# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Auto-discover coding standards from codebase analysis.

Extracts naming conventions, patterns, error handling, and architectural
decisions via AST parsing with recency weighting.  Supports HITL document
review before storing confirmed standards in the DB for prompt injection.
"""
