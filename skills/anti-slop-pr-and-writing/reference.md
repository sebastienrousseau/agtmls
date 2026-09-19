<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Anti-Slop Reference & Catalog

Detailed catalog of anti-patterns and concrete before and after transformations.

## Before and after examples

### 1. PR descriptions and Pull Requests

#### Slop (Before)
> 🚀 **Exciting Updates!**
> In today's fast-paced microservice architecture, performance is key. It's not just about speed; it's about reliability.
> In this PR, we dive deep into the cache layer:
> - ✨ Updated cache.py
> - ⚡ Improved query execution
> Let me know your thoughts!

#### Clean (After)
> Replaces in-memory LRU cache with Redis backend to prevent cache thrashing across worker restarts.
>
> Benchmark results:
> - P99 latency reduced from 42ms to 6ms under 10k RPS load.
> - Fixes #142.

### 2. Git Commit Messages

#### Slop (Before)
> fix: I fixed the annoying bug where the token was expiring too early and causing failures. Sorry about that!

#### Clean (After)
> fix(auth): refresh session tokens 5 minutes prior to expiry
>
> Prevents intermittent 401 errors during active user workflows by
> issuing background refreshes before token invalidation.
>
> Fixes #88

### 3. Code Comments

#### Slop (Before)
```python
# Check if user is None
if user is None:
    # Return 404 error
    return jsonify({"error": "User not found"}), 404
```

#### Clean (After)
```python
if user is None:
    return jsonify({"error": "User not found"}), 404
```
