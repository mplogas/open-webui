# Collection Open WebUI Tools

## Web Content Extractor

### Exposed Tool capabilities

1. **`fetch_url_content`** - Extract clean content from a single URL
2. **`fetch_multiple_urls`** - Batch process multiple URLs at once

### Features

- **Multiple extraction engines**: Trafilatura (articles), Readability (Mozilla algorithm), Basic (BeautifulSoup)
- **Auto-fallback**: Tries best method first, degrades gracefully
- **Local processing**: No external APIs, no rate limits. Well... yeah... I mean you will get throttled at some point :)
- **Markdown output**: LLMs love *.md
- **Automatic citations**: Includes source URL, title, author, date metadata
- **Configurable**: User controls extraction method, link inclusion, metadata display

### USage

**Single page:**
```
"Fetch https://en.wikipedia.org/wiki/Python_(programming_language) and summarize the key features"
"Extract the installation instructions from https://github.com/project/readme"
"Read https://arxiv.org/abs/2311.12345 and explain the methodology in simple terms"
```

**Multiple pages:**
```
"Compare these articles: https://site1.com/view1, https://site2.com/view2"
```


## Paperless-ngx Integration

### Exposed Tool capabilities

1. **`search_documents`** - General full-text search
2. **`search_by_tags`** - Filter by tags (any or all)
3. **`search_by_type_and_tags`** - Filter by document type + tags
4. **`search_by_correspondent`** - Filter by sender/source
5. **`list_all_tags`** - See available tags
6. **`list_document_types`** - See available types
7. **`list_correspondents`** - See available correspondents
8. **`get_document_by_id`** - Direct document access
9. **`find_similar_documents`** - ML-based similarity
10. **`advanced_document_search`** - Kitchen sink with all filters

### Features

- **Natural language search**: Resolves tag/type/correspondent names to IDs automatically
- **Full content extraction**: Retrieves complete document text for further analysis
- **Smart filtering**: Combine multiple criteria (type + tags + correspondent + dates)
- **Automatic citations**: Creates proper references with metadata
- **Real-time status**: Progress updates during search and retrieval
- **Configurable limits**: Control result count and content size

### Usage

**By type and tags:**
```
"Show me all invoices tagged framework and 2025"
"Find receipts with tag 'business expense'"
```

**By correspondent and type:**
```
"Find all invoices from Framework"
"Show me contracts from ACME Corporation"
```
→ Uses `search_by_correspondent(correspondent="Framework", document_type="invoice")`

**By correspondent, type, AND tags:**
```
"Show me all invoices from Framework with tag 'computer' from 2025"
```
→ Uses `search_by_correspondent(correspondent="Framework", document_type="invoice", tags="computer", query="2025")`

**Discovery functions:**
```
"What document types do I have?"
"List all my correspondents"
"Show me all available tags"
```

## GitHub Reader

## Core Functions

1. **`read_file`** - Read any file from a repository (public or private)
2. **`list_repository_files`** - Browse repository file structure
3. **`search_code`** - Search for code across GitHub
4. **`get_repository_info`** - Get repository metadata and statistics
5. **`list_my_gists`** - List all your gists
6. **`get_gist`** - Read a gist by ID (with syntax highlighting)
7. **`create_gist`** - Create a new gist (public or secret)
8. **`update_gist`** - Update existing gist content
9. **`delete_gist`** - Delete a gist


## Key Features

- **Public & private repos**: Works with any repository you have access to
- **Syntax highlighting**: Automatic language detection for code display
- **Line numbers**: Optional line numbering for code review
- **Tree browsing**: Recursive or non-recursive directory listing
- **Code search**: Find specific functions, patterns, or implementations
- **Large file handling**: Size limits to prevent memory issues
- **Automatic citations**: Links back to source files on GitHub

## Usage Examples

**Read files:**
```
"Read the main.py file from myusername/my-project"
"Show me the README from torvalds/linux"
"Read src/components/Header.tsx from facebook/react branch next"
```

**Browse structure:**
```
"List all files in microsoft/vscode"
"Show me the directory structure of my-org/private-repo"
"What files are in the src/ directory of rust-lang/rust?"
```

**Search code:**
```
"Search for 'async def' in my Python repositories"
"Find examples of useEffect in repo facebook/react"
"Search for JWT authentication code in language:python"
```

**Repository info:**
```
"Tell me about the repository kubernetes/kubernetes"
"What languages are used in tensorflow/tensorflow?"
"Show me stats for my-username/my-private-repo"
```

**Code analysis:**
```
"Read the authentication module from my-org/api-server and explain how it works"
"Compare the implementation in file1.py and file2.py from my-repo"
"Find all API endpoints in my-backend/server and list them"
```

**List your gists:**
```
"Show me my recent gists"
"List my GitHub gists"
```

**Read a gist:**
```
"Get gist abc123def456"
"Show me the content of gist abc123"
```

**Create a gist:**
```
"Create a public gist with description 'Python helper functions' and files: helpers.py=def hello(): print('hi')|||test.py=print('test')"
```

**Update a gist:**
```
"Update gist abc123 with new description 'Updated helpers'"
"Update gist abc123 files: helpers.py=def hello(): print('updated')"
```

**Delete a gist:**
```
"Delete gist abc123"
```

The file format for `files` parameter is: `filename1.ext=content1|||filename2.ext=content2` - this allows multiple files per gist!


## Setup

1. **For public repos:** Works immediately, no configuration needed
2. **For private repos:** 
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (full control of private repositories), `gists` (full control of gists) and `workflow` 
   - Copy token and add to tool settings
