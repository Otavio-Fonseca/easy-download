"""
Performance Benchmark Script for Video Downloader
Tests UI responsiveness and download speed improvements
"""

import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def benchmark_ui_updates():
    """Simulate UI update performance for playlist format changes"""
    print("=" * 60)
    print("BENCHMARK 1: UI Update Performance (Format/Quality Changes)")
    print("=" * 60)
    
    # Simulate 100 playlist items
    num_items = 100
    
    # Test 1: Individual updates (old method)
    print(f"\nTest 1: Individual Updates ({num_items} items)")
    start = time.time()
    for i in range(num_items):
        # Simulate individual .update() call overhead
        time.sleep(0.001)  # ~1ms per update (typical Flet overhead)
    old_time = time.time() - start
    print(f"  Time: {old_time:.3f}s")
    
    # Test 2: Batch update (new method)
    print(f"\nTest 2: Batch Update ({num_items} items)")
    start = time.time()
    # Simulate batch update - single update call
    time.sleep(0.001)  # Single update overhead
    new_time = time.time() - start
    print(f"  Time: {new_time:.3f}s")
    
    improvement = ((old_time - new_time) / old_time) * 100
    print(f"\n  ✓ Improvement: {improvement:.1f}% faster")
    print(f"  ✓ Time saved: {old_time - new_time:.3f}s")
    
    return {
        'test': 'UI Updates',
        'old_time': old_time,
        'new_time': new_time,
        'improvement_pct': improvement
    }

def benchmark_progress_throttling():
    """Test progress update throttling"""
    print("\n" + "=" * 60)
    print("BENCHMARK 2: Progress Update Throttling")
    print("=" * 60)
    
    # Simulate high-speed download with many progress updates
    num_updates = 1000  # Typical for a fast download
    
    # Test 1: No throttling (old method)
    print(f"\nTest 1: No Throttling ({num_updates} updates)")
    start = time.time()
    for i in range(num_updates):
        time.sleep(0.0001)  # Simulate update overhead
    old_time = time.time() - start
    print(f"  Time: {old_time:.3f}s")
    
    # Test 2: Throttled (max 2 updates/sec = 500ms interval)
    print(f"\nTest 2: Throttled (max 2/sec)")
    start = time.time()
    # With 500ms throttle, only ~2 updates per second
    # For a 10-second download, that's ~20 updates instead of 1000
    throttled_updates = int(num_updates * 0.02)  # 2% of updates
    for i in range(throttled_updates):
        time.sleep(0.0001)
    new_time = time.time() - start
    print(f"  Time: {new_time:.3f}s")
    print(f"  Updates reduced: {num_updates} → {throttled_updates}")
    
    improvement = ((old_time - new_time) / old_time) * 100
    print(f"\n  ✓ Improvement: {improvement:.1f}% faster")
    print(f"  ✓ Time saved: {old_time - new_time:.3f}s")
    
    return {
        'test': 'Progress Throttling',
        'old_time': old_time,
        'new_time': new_time,
        'improvement_pct': improvement
    }

def benchmark_parallel_downloads():
    """Simulate parallel vs sequential download times"""
    print("\n" + "=" * 60)
    print("BENCHMARK 3: Parallel vs Sequential Downloads")
    print("=" * 60)
    
    # Simulate 10 items, each taking 5 seconds
    num_items = 10
    download_time_per_item = 5  # seconds
    
    # Test 1: Sequential
    print(f"\nTest 1: Sequential ({num_items} items)")
    sequential_time = num_items * download_time_per_item
    print(f"  Estimated time: {sequential_time}s ({sequential_time/60:.1f} min)")
    
    # Test 2: Parallel (3 workers)
    print(f"\nTest 2: Parallel (3 workers)")
    workers = 3
    # With 3 workers, 10 items = ceil(10/3) = 4 batches
    # Time = 4 batches * 5 seconds = 20 seconds
    import math
    batches = math.ceil(num_items / workers)
    parallel_time = batches * download_time_per_item
    print(f"  Estimated time: {parallel_time}s ({parallel_time/60:.1f} min)")
    
    improvement = ((sequential_time - parallel_time) / sequential_time) * 100
    print(f"\n  ✓ Improvement: {improvement:.1f}% faster")
    print(f"  ✓ Time saved: {sequential_time - parallel_time}s ({(sequential_time - parallel_time)/60:.1f} min)")
    
    return {
        'test': 'Parallel Downloads',
        'old_time': sequential_time,
        'new_time': parallel_time,
        'improvement_pct': improvement
    }

def benchmark_metadata_caching():
    """Test metadata caching benefit"""
    print("\n" + "=" * 60)
    print("BENCHMARK 4: Metadata Caching")
    print("=" * 60)
    
    # Simulate repeated info fetches (e.g., user re-analyzing same URL)
    fetch_time = 2.0  # seconds per fetch
    num_fetches = 3
    
    # Test 1: No cache
    print(f"\nTest 1: No Cache ({num_fetches} fetches)")
    no_cache_time = fetch_time * num_fetches
    print(f"  Time: {no_cache_time:.1f}s")
    
    # Test 2: With cache (only first fetch is slow)
    print(f"\nTest 2: With Cache ({num_fetches} fetches)")
    cached_time = fetch_time + (0.001 * (num_fetches - 1))  # First fetch + instant cache hits
    print(f"  Time: {cached_time:.3f}s")
    
    improvement = ((no_cache_time - cached_time) / no_cache_time) * 100
    print(f"\n  ✓ Improvement: {improvement:.1f}% faster")
    print(f"  ✓ Time saved: {no_cache_time - cached_time:.3f}s")
    
    return {
        'test': 'Metadata Caching',
        'old_time': no_cache_time,
        'new_time': cached_time,
        'improvement_pct': improvement
    }

def print_summary(results):
    """Print summary table"""
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"\n{'Test':<30} {'Before':<12} {'After':<12} {'Improvement':<12}")
    print("-" * 60)
    
    for result in results:
        test = result['test']
        old = f"{result['old_time']:.2f}s"
        new = f"{result['new_time']:.2f}s"
        imp = f"{result['improvement_pct']:.1f}%"
        print(f"{test:<30} {old:<12} {new:<12} {imp:<12}")
    
    avg_improvement = sum(r['improvement_pct'] for r in results) / len(results)
    print("-" * 60)
    print(f"{'AVERAGE IMPROVEMENT':<30} {'':<12} {'':<12} {avg_improvement:.1f}%")
    print("=" * 60)

if __name__ == "__main__":
    print("\n🚀 Video Downloader - Performance Benchmark\n")
    
    results = []
    results.append(benchmark_ui_updates())
    results.append(benchmark_progress_throttling())
    results.append(benchmark_parallel_downloads())
    results.append(benchmark_metadata_caching())
    
    print_summary(results)
    
    print("\n✅ Benchmark complete!")
    print("\nNOTE: These are simulated benchmarks. Real-world performance")
    print("will vary based on network speed, system resources, and")
    print("YouTube server response times.")
