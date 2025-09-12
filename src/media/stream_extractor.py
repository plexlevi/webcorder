#!/usr/bin/env python3
"""
Hybrid Stream Extractor - Lightweight requests-based extraction
Strategy:
- Chaturbate: Pure requests (fast, no JS needed)
- XHamsterLive: Fast requests with performer ID + tokens
- Other sites: Auto-detect best method
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import re
import time
from typing import Optional, Dict, List
from urllib.parse import urlparse

class HybridStreamExtractor:
    def __init__(self):
        self.site_strategies = {
            'chaturbate.com': 'requests',
            'xhamsterlive.com': 'fast_requests', 
            'hu.xhamsterlive.com': 'fast_requests',
        }
        
        # Performance tracking
        self.stats = {
            'requests_extractions': 0,
            'fast_requests_extractions': 0,
            'total_time': 0.0,
            'success_rate': 0.0
        }
    
    def get_extraction_strategy(self, url: str) -> str:
        """Determine the best extraction strategy for a URL"""
        domain = urlparse(url).netloc.lower()
        
        # Check exact domain matches
        if domain in self.site_strategies:
            return self.site_strategies[domain]
        
        # Check partial domain matches
        for site_domain, strategy in self.site_strategies.items():
            if site_domain in domain:
                return strategy
        
        # Default strategy: try requests first
        return 'requests'
    
    def extract_with_fast_requests(self, url: str) -> Optional[str]:
        """Ultra-fast extraction: get performer ID with requests + try tokens"""
        print(f"⚡ FAST REQUESTS MODE: {urlparse(url).netloc}")
        
        start_time = time.time()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            content = response.text
            
            # Performer ID keresése a HTML-ben
            performer_id_patterns = [
                r'/thumbs/\d+/(\d+)',
                r'performer[_-]?id[\'\":\s]*(\d+)',
                r'model[_-]?id[\'\":\s]*(\d+)',
                r'/hls/(\d+)/',
                r'doppiocdn\.live/hls/(\d+)/',
                r'data-performer-id[\'\"]*=[\'\"](\d+)',
                r'performerId[\'\"]*:[\'\"](\d+)'
            ]
            
            performer_id = None
            for pattern in performer_id_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    performer_id = matches[0]
                    print(f"   ⚡ Found performer ID: {performer_id}")
                    break
            
            if performer_id:
                # Azonnal próbáljunk tokenes URL-eket
                tokened_url = self._try_with_tokens(performer_id)
                if tokened_url:
                    elapsed = time.time() - start_time
                    print(f"   ✅ Fast extraction in {elapsed:.2f}s")
                    self.stats['fast_requests_extractions'] += 1
                    return tokened_url
            
            elapsed = time.time() - start_time
            print(f"   ❌ No performer ID found in {elapsed:.2f}s")
            return None
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   ❌ Fast requests error in {elapsed:.2f}s: {e}")
            return None
    
    def extract_with_requests(self, url: str) -> Optional[str]:
        """Fast extraction using pure requests (no JavaScript)"""
        print(f"⚡ REQUESTS MODE: {urlparse(url).netloc}")
        
        start_time = time.time()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            content = response.text
            
            # Enhanced pattern matching for different sites
            stream_patterns = [
                # Chaturbate patterns (works great with requests only)
                r'https?://[^\s"\']*edge[^\s"\']*\.live\.mmcdn\.com[^\s"\']*\.m3u8[^\s"\']*',
                r'https?://[^\s"\']*\.live\.mmcdn\.com[^\s"\']*playlist\.m3u8[^\s"\']*',
                
                # General HLS patterns
                r'https?://[^\s"\']*\.m3u8[^\s"\']*',
                r'https?://[^\s"\']*playlist\.m3u8[^\s"\']*',
                r'https?://[^\s"\']*master\.m3u8[^\s"\']*',
                
                # Streaming CDN patterns
                r'https?://[^\s"\']*streaming[^\s"\']*\.[^\s"\']+[^\s"\']*',
                r'https?://[^\s"\']*edge[^\s"\']*\.[^\s"\']+[^\s"\']*',
                r'https?://[^\s"\']*cdn[^\s"\']*\.[^\s"\']+[^\s"\']*',
                
                # Site-specific patterns
                r'https?://[^\s"\']*doppiocdn\.com[^\s"\']*',
                r'https?://[^\s"\']*livemediahost\.com[^\s"\']*'
            ]
            
            found_urls = []
            for pattern in stream_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                found_urls.extend(matches)
            
            if found_urls:
                # Clean and prioritize URLs
                clean_urls = self._clean_and_prioritize_urls(found_urls)
                
                if clean_urls:
                    elapsed = time.time() - start_time
                    print(f"   ✅ Found {len(clean_urls)} URLs in {elapsed:.2f}s")
                    self.stats['requests_extractions'] += 1
                    return clean_urls[0]
            
            elapsed = time.time() - start_time
            print(f"   ❌ No URLs found in {elapsed:.2f}s")
            return None
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   ❌ Error in {elapsed:.2f}s: {e}")
            return None
    
    def _try_with_tokens(self, performer_id: str) -> Optional[str]:
        """Megpróbál tokeneket hozzáadni egy alap URL-hez"""
        import requests
        
        print(f"   🔑 Trying with tokens for performer ID: {performer_id}")
        
        base_url = f"https://edge-hls.doppiocdn.live/hls/{performer_id}/master/{performer_id}_auto.m3u8"
        
        # Különböző token kombinációk próbálása
        token_patterns = [
            "?playlistType=standard&psch=v1&pkey=Thoohie4ieRaGaeb",
            "?playlistType=standard&psch=v2&pkey=Thoohie4ieRaGaeb", 
            "?playlistType=m3u8&psch=v1&pkey=Thoohie4ieRaGaeb",
            "?pkey=Thoohie4ieRaGaeb&psch=v1",
            "?pkey=default&psch=v1&playlistType=standard",
            "?token=live&psch=v1",
            "?auth=token&playlistType=standard",
            "?live=true&format=m3u8"
        ]
        
        for token_pattern in token_patterns:
            tokened_url = base_url + token_pattern
            try:
                print(f"   🔑 Testing: {tokened_url}")
                response = requests.head(tokened_url, timeout=5)
                if response.status_code == 200:
                    print(f"   ✅ WORKING WITH TOKENS: {tokened_url}")
                    return tokened_url
                else:
                    print(f"   ❌ Token failed ({response.status_code}): {token_pattern}")
            except Exception as e:
                print(f"   ❌ Token error: {e}")
                continue
        
        print(f"   ❌ No working tokens found for {performer_id}")
        return None
    
    def _clean_and_prioritize_urls(self, urls: List[str]) -> List[str]:
        """Clean URLs and prioritize by quality/relevance"""
        
        def is_valid_stream_url(url: str) -> bool:
            """Check if URL is a valid stream (not image/other formats)"""
            url_lower = url.lower()
            
            # Skip image URLs
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
            for ext in image_extensions:
                if ext in url_lower:
                    return False
            
            # Skip image CDN domains
            image_domains = ['jpeg.live.', 'jpg.live.', 'png.live.', 'img.', 'image.', 'thumb.', 'preview.']
            for domain in image_domains:
                if domain in url_lower:
                    return False
            
            # Only accept known streaming formats
            streaming_indicators = ['.m3u8', '.mp4', '.flv', '.webm', '.mkv', 'playlist', 'master', 'stream']
            return any(indicator in url_lower for indicator in streaming_indicators)
        
        def stream_priority(url: str) -> int:
            """Calculate priority score for a stream URL"""
            score = 0
            
            # FIRST: Skip invalid streams (images, etc.)
            if not is_valid_stream_url(url):
                return -1000  # Very low priority for invalid streams
            
            # Prefer .m3u8 URLs
            if '.m3u8' in url:
                score += 100
                
            # Prefer playlist URLs
            if 'playlist' in url:
                score += 50
                
            # Prefer master URLs  
            if 'master' in url:
                score += 40
                
            # Prefer edge servers
            if 'edge' in url:
                score += 30
                
            # Prefer live CDNs
            if '.live.' in url:
                score += 20
                
            # Prefer HTTPS
            if url.startswith('https://'):
                score += 10
                
            return score
        
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        
        for url in urls:
            # Clean URL - fix encoding issues
            cleaned_url = url.strip().rstrip('",\'')
            
            # Fix Unicode escapes that appear in Chaturbate URLs
            if '\\u002D' in cleaned_url:
                cleaned_url = cleaned_url.replace('\\u002D', '-')
            if '\\u002d' in cleaned_url:
                cleaned_url = cleaned_url.replace('\\u002d', '-')
            
            # Remove trailing quotes and escapes
            if cleaned_url.endswith('\\u0022'):
                cleaned_url = cleaned_url[:-6]  # Remove \u0022
            if cleaned_url.endswith('\\"'):
                cleaned_url = cleaned_url[:-2]  # Remove \"
            if cleaned_url.endswith('"'):
                cleaned_url = cleaned_url[:-1]  # Remove "
                
            # Fix escaped characters
            cleaned_url = cleaned_url.replace('\\u002F', '/')
            cleaned_url = cleaned_url.replace('\\u003A', ':')
            cleaned_url = cleaned_url.replace('\\/', '/')
            
            # Skip very short or obviously invalid URLs
            if len(cleaned_url) < 10 or not cleaned_url.startswith('http'):
                continue
            
            # Skip non-streaming URLs (images, etc.)
            if not is_valid_stream_url(cleaned_url):
                continue
                
            # Skip duplicates
            if cleaned_url in seen:
                continue
                
            seen.add(cleaned_url)
            unique_urls.append(cleaned_url)

        # Sort by priority, but filter out invalid streams (negative priority)
        sorted_urls = sorted(unique_urls, key=stream_priority, reverse=True)
        return [url for url in sorted_urls if stream_priority(url) > 0]
    
    def extract_stream_url(self, url: str) -> Optional[str]:
        """Main extraction method with hybrid strategy"""
        print(f"\n🎯 HYBRID EXTRACTOR: {url}")
        print("=" * 60)
        
        start_time = time.time()
        strategy = self.get_extraction_strategy(url)
        
        print(f"📋 Strategy: {strategy.upper()}")
        
        result = None
        
        if strategy == 'requests':
            result = self.extract_with_requests(url)
        elif strategy == 'fast_requests':
            result = self.extract_with_fast_requests(url)
        
        elapsed = time.time() - start_time
        self.stats['total_time'] += elapsed
        
        if result:
            print(f"✅ SUCCESS: {result}")
            return result
        else:
            print(f"❌ FAILED: No stream URL found")
            return None
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        total_extractions = self.stats['requests_extractions'] + self.stats['fast_requests_extractions']
        
        return {
            'total_extractions': total_extractions,
            'requests_extractions': self.stats['requests_extractions'],
            'fast_requests_extractions': self.stats['fast_requests_extractions'],
            'requests_percentage': (self.stats['requests_extractions'] / total_extractions * 100) if total_extractions > 0 else 0,
            'average_time': self.stats['total_time'] / total_extractions if total_extractions > 0 else 0,
            'total_time': self.stats['total_time']
        }
    
    def cleanup(self):
        """Clean up resources (no-op without Selenium)"""
        pass
