import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any

class LoadTester:
    """Simple load testing framework for FastAPI"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []
    
    async def make_request(self, session: aiohttp.ClientSession, endpoint: str, method: str = "GET", data: Dict = None):
        """Make a single request and measure response time"""
        start_time = time.time()
        try:
            async with session.request(method, f"{self.base_url}{endpoint}", json=data) as response:
                response_time = time.time() - start_time
                status = response.status
                
                return {
                    "endpoint": endpoint,
                    "method": method,
                    "status": status,
                    "response_time": response_time,
                    "success": 200 <= status < 400
                }
        except Exception as e:
            return {
                "endpoint": endpoint,
                "method": method,
                "status": 0,
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def run_load_test(
        self, 
        endpoint: str, 
        concurrent_users: int = 10, 
        requests_per_user: int = 10,
        method: str = "GET",
        data: Dict = None
    ):
        """Run load test with specified parameters"""
        
        print(f"🚀 Starting load test:")
        print(f"   Endpoint: {endpoint}")
        print(f"   Concurrent users: {concurrent_users}")
        print(f"   Requests per user: {requests_per_user}")
        print(f"   Total requests: {concurrent_users * requests_per_user}")
        
        async def user_requests(session: aiohttp.ClientSession):
            user_results = []
            for _ in range(requests_per_user):
                result = await self.make_request(session, endpoint, method, data)
                user_results.append(result)
            return user_results
        
        # Run concurrent users
        async with aiohttp.ClientSession() as session:
            tasks = [user_requests(session) for _ in range(concurrent_users)]
            all_results = await asyncio.gather(*tasks)
        
        # Flatten results
        self.results = [result for user_results in all_results for result in user_results]
        
        return self.analyze_results()
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze load test results"""
        
        if not self.results:
            return {"error": "No results to analyze"}
        
        response_times = [r["response_time"] for r in self.results]
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = [r for r in self.results if not r["success"]]
        
        analysis = {
            "total_requests": len(self.results),
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / len(self.results) * 100,
            "response_times": {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "p95": self._percentile(response_times, 95),
                "p99": self._percentile(response_times, 99)
            },
            "requests_per_second": len(self.results) / sum(response_times) if sum(response_times) > 0 else 0
        }
        
        # Status code distribution
        status_codes = {}
        for result in self.results:
            status = result["status"]
            status_codes[status] = status_codes.get(status, 0) + 1
        analysis["status_codes"] = status_codes
        
        return analysis
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_results(self, analysis: Dict[str, Any]):
        """Print formatted results"""
        print("\n📊 Load Test Results:")
        print("=" * 50)
        print(f"Total Requests: {analysis['total_requests']}")
        print(f"Successful: {analysis['successful_requests']}")
        print(f"Failed: {analysis['failed_requests']}")
        print(f"Success Rate: {analysis['success_rate']:.2f}%")
        print(f"Requests/Second: {analysis['requests_per_second']:.2f}")
        
        print("\n⏱️  Response Times:")
        rt = analysis['response_times']
        print(f"Min: {rt['min']:.3f}s")
        print(f"Max: {rt['max']:.3f}s") 
        print(f"Mean: {rt['mean']:.3f}s")
        print(f"Median: {rt['median']:.3f}s")
        print(f"95th percentile: {rt['p95']:.3f}s")
        print(f"99th percentile: {rt['p99']:.3f}s")
        
        print(f"\n📈 Status Codes:")
        for status, count in analysis['status_codes'].items():
            print(f"{status}: {count}")

# Usage example
async def main():
    tester = LoadTester("http://localhost:8000")
    
    # Test health endpoint
    analysis = await tester.run_load_test(
        endpoint="/health",
        concurrent_users=5,
        requests_per_user=20
    )
    
    tester.print_results(analysis)

if __name__ == "__main__":
    asyncio.run(main())
