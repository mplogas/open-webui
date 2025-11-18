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

### 
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

## Alpha Vantage integration
