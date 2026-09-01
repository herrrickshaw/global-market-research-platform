#!/usr/bin/env python3
"""
Setup benchmark dataset by fetching sample documents
"""

import os
import json
from pathlib import Path
from urllib.request import urlopen

BENCHMARK_DIR = Path.home() / "benchmarks"

# Sample document sources (freely available)
SAMPLE_DOCS = {
    'pdfs': [
        # ArXiv papers (ML)
        'https://arxiv.org/pdf/2301.00001.pdf',
        'https://arxiv.org/pdf/2302.00001.pdf',
        # Add more as needed
    ],
    'json': [
        # GitHub API schema
        ('https://docs.github.com/en/rest/overview/api-preview-notices?apiVersion=2022-11-28', 'github_api.json'),
        # OpenAI API
        ('https://platform.openai.com/docs/api-reference', 'openai_api.json'),
    ],
    'html': [
        # Wikipedia article
        ('https://en.wikipedia.org/wiki/Machine_learning', 'wikipedia_ml.html'),
        # MDN docs
        ('https://developer.mozilla.org/en-US/docs/Web/JavaScript', 'mdn_javascript.html'),
    ]
}

def create_sample_json_files():
    """Create sample JSON files for testing"""
    json_dir = BENCHMARK_DIR / 'json'
    json_dir.mkdir(exist_ok=True)

    samples = [
        {
            'name': 'sample_api.json',
            'data': {
                'api': 'Sample API',
                'version': '1.0',
                'endpoints': [
                    {'path': '/users', 'method': 'GET', 'description': 'List users'},
                    {'path': '/users/{id}', 'method': 'GET', 'description': 'Get user'},
                    {'path': '/users', 'method': 'POST', 'description': 'Create user'},
                ] * 10  # Repeat to make larger
            }
        },
        {
            'name': 'sample_config.json',
            'data': {
                'application': {
                    'name': 'MyApp',
                    'version': '2.0',
                    'database': {
                        'host': 'localhost',
                        'port': 5432,
                        'credentials': {'user': 'admin', 'password': '***'},
                    },
                    'services': [
                        {'name': 'service1', 'url': 'http://localhost:8000'},
                        {'name': 'service2', 'url': 'http://localhost:8001'},
                    ] * 5
                }
            }
        },
        {
            'name': 'sample_data.json',
            'data': {
                'records': [
                    {
                        'id': i,
                        'name': f'Record {i}',
                        'email': f'user{i}@example.com',
                        'created_at': '2024-01-01T00:00:00Z',
                        'metadata': {
                            'source': 'api',
                            'version': 1,
                            'tags': ['sample', 'test', 'benchmark']
                        }
                    }
                    for i in range(20)
                ]
            }
        }
    ]

    for sample in samples:
        filepath = json_dir / sample['name']
        with open(filepath, 'w') as f:
            json.dump(sample['data'], f, indent=2)
        print(f"✓ Created {sample['name']}")


def create_sample_code_files():
    """Create sample code files for testing"""
    code_dir = BENCHMARK_DIR / 'code'
    code_dir.mkdir(exist_ok=True)

    samples = {
        'sample.py': '''"""
Sample Python module for token optimization testing
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class User:
    """User data model"""
    id: int
    name: str
    email: str
    created_at: str


class UserManager:
    """Manage user operations"""

    def __init__(self, db_url: str):
        """Initialize with database URL"""
        self.db_url = db_url
        self.users: Dict[int, User] = {}

    def create_user(self, name: str, email: str) -> User:
        """Create new user"""
        user_id = len(self.users) + 1
        user = User(id=user_id, name=name, email=email, created_at='2024-01-01')
        self.users[user_id] = user
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    def list_users(self) -> List[User]:
        """List all users"""
        return list(self.users.values())

    def delete_user(self, user_id: int) -> bool:
        """Delete user"""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False


# Example usage
if __name__ == '__main__':
    manager = UserManager('sqlite:///users.db')
    manager.create_user('Alice', 'alice@example.com')
    manager.create_user('Bob', 'bob@example.com')
    print(manager.list_users())
''' * 3,  # Repeat for size
        'sample.js': '''/**
 * Sample JavaScript module for token optimization testing
 */

class UserAPI {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }

    async getUsers() {
        const response = await fetch(`${this.baseUrl}/users`);
        return response.json();
    }

    async createUser(userData) {
        const response = await fetch(`${this.baseUrl}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        return response.json();
    }

    async updateUser(userId, userData) {
        const response = await fetch(`${this.baseUrl}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        return response.json();
    }

    async deleteUser(userId) {
        const response = await fetch(`${this.baseUrl}/users/${userId}`, {
            method: 'DELETE'
        });
        return response.ok;
    }
}

// Export for use
module.exports = UserAPI;
''' * 3,
    }

    for filename, content in samples.items():
        filepath = code_dir / filename
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✓ Created {filename}")


def create_sample_html_files():
    """Create sample HTML files for testing"""
    html_dir = BENCHMARK_DIR / 'html'
    html_dir.mkdir(exist_ok=True)

    sample_html = '''<!DOCTYPE html>
<html>
<head>
    <title>Sample Article</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width">
</head>
<body>
    <h1>Introduction to Machine Learning</h1>
    <p>Machine learning is a subset of artificial intelligence...</p>
    <h2>What is Machine Learning?</h2>
    <p>Machine learning enables computers to learn from data without being explicitly programmed.</p>
    <h3>Types of Machine Learning</h3>
    <ul>
        <li>Supervised Learning: Learn from labeled data</li>
        <li>Unsupervised Learning: Find patterns in unlabeled data</li>
        <li>Reinforcement Learning: Learn through interaction</li>
    </ul>
    <h2>Applications</h2>
    <p>Machine learning has numerous applications across industries...</p>
    <h2>Conclusion</h2>
    <p>The field of machine learning continues to evolve...</p>
</body>
</html>
''' * 3

    for i in range(1, 4):
        filepath = html_dir / f'sample_article_{i}.html'
        with open(filepath, 'w') as f:
            f.write(sample_html)
        print(f"✓ Created sample_article_{i}.html")


def create_sample_docx_placeholder():
    """Create placeholder files for DOCX (note: actual DOCX creation requires python-docx)"""
    docx_dir = BENCHMARK_DIR / 'docx'
    docx_dir.mkdir(exist_ok=True)

    # Create text files as placeholders (can be manually converted to DOCX)
    sample_text = '''# Technical Specification

## Overview
This document describes the technical architecture and design of the system.

## Architecture
The system is built on a microservices architecture with the following components:
- API Gateway
- User Service
- Product Service
- Order Service
- Payment Service

## API Endpoints
- GET /users - List all users
- POST /users - Create new user
- GET /products - List products
- POST /orders - Create order

## Database Schema
The database includes the following tables:
- users
- products
- orders
- order_items

## Security
- All API endpoints require authentication
- Passwords are hashed using bcrypt
- All data is encrypted in transit using TLS

## Performance Requirements
- P99 latency < 200ms
- Availability > 99.9%
- Support for 10k concurrent users
'''

    for i in range(1, 4):
        filepath = docx_dir / f'sample_spec_{i}.txt'
        with open(filepath, 'w') as f:
            f.write(sample_text)
        print(f"✓ Created sample_spec_{i}.txt (convert to DOCX manually)")


def create_sample_pdf_placeholder():
    """Create placeholder files for PDFs (actual PDF creation requires reportlab)"""
    pdf_dir = BENCHMARK_DIR / 'pdfs'
    pdf_dir.mkdir(exist_ok=True)

    # Create text placeholders
    sample_content = '''Research Paper: Token Optimization in Language Models

Abstract
This paper presents a comprehensive study of token optimization techniques for large language models.

1. Introduction
Token efficiency is crucial for deploying large language models in production environments.

2. Methodology
We evaluate various token optimization strategies including:
- Prompt compression
- Context pruning
- Caching strategies
- Model routing

3. Results
Our findings show significant improvements in token efficiency across multiple benchmarks.

4. Conclusion
Token optimization is a critical area for making language models more practical.

References
[1] Smith et al., 2023. Token Optimization in LLMs
[2] Johnson et al., 2023. Efficient Transformers
'''

    for i in range(1, 4):
        filepath = pdf_dir / f'research_paper_{i}.txt'
        with open(filepath, 'w') as f:
            f.write(sample_content)
        print(f"✓ Created research_paper_{i}.txt (convert to PDF manually)")


def main():
    print("📚 Setting up benchmark dataset...")
    print()

    # Create all directories
    for dir_name in ['pdfs', 'docx', 'json', 'html', 'code', 'results']:
        (BENCHMARK_DIR / dir_name).mkdir(exist_ok=True)

    # Create sample files
    print("Creating sample files:")
    create_sample_json_files()
    create_sample_code_files()
    create_sample_html_files()
    create_sample_docx_placeholder()
    create_sample_pdf_placeholder()

    print()
    print("✅ Benchmark dataset setup complete!")
    print()
    print("Next steps:")
    print("1. Convert .txt files to proper formats (DOCX, PDF)")
    print("2. Run: python run_benchmark.py")
    print()
    print("📁 Files created in: ~/benchmarks/")


if __name__ == '__main__':
    main()
