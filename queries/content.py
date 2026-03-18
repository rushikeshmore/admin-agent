"""
GraphQL query and mutation strings for Content (Pages, Blogs, Articles, Redirects).
"""

# ─── Pages ────────────────────────────────────────────────────────────────────

QUERY_PAGE = """
query GetPage($id: ID!) {
  page(id: $id) {
    id
    title
    handle
    body
    bodySummary
    isPublished
    publishedAt
    createdAt
    updatedAt
    templateSuffix
  }
}
"""

QUERY_PAGES = """
query ListPages($first: Int!, $after: String) {
  pages(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        isPublished
        createdAt
        updatedAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

MUTATION_PAGE_CREATE = """
mutation PageCreate($page: PageCreateInput!) {
  pageCreate(page: $page) {
    page {
      id
      title
      handle
      isPublished
    }
    userErrors { field message }
  }
}
"""

MUTATION_PAGE_UPDATE = """
mutation PageUpdate($id: ID!, $page: PageUpdateInput!) {
  pageUpdate(id: $id, page: $page) {
    page {
      id
      title
      handle
      isPublished
      updatedAt
    }
    userErrors { field message }
  }
}
"""

MUTATION_PAGE_DELETE = """
mutation PageDelete($id: ID!) {
  pageDelete(id: $id) {
    deletedPageId
    userErrors { field message }
  }
}
"""

# ─── Blogs & Articles ─────────────────────────────────────────────────────────

QUERY_BLOGS = """
query ListBlogs($first: Int!) {
  blogs(first: $first) {
    edges {
      node {
        id
        title
        handle
      }
    }
  }
}
"""

QUERY_ARTICLES = """
query ListArticles($first: Int!, $after: String, $query: String) {
  articles(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        title
        handle
        tags
        isPublished
        publishedAt
        blog { id title }
        author { name }
        summary
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# ─── URL Redirects ────────────────────────────────────────────────────────────

QUERY_REDIRECTS = """
query ListRedirects($first: Int!, $after: String) {
  urlRedirects(first: $first, after: $after) {
    edges {
      node {
        id
        path
        target
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

MUTATION_REDIRECT_CREATE = """
mutation RedirectCreate($urlRedirect: UrlRedirectInput!) {
  urlRedirectCreate(urlRedirect: $urlRedirect) {
    urlRedirect {
      id
      path
      target
    }
    userErrors { field message }
  }
}
"""

MUTATION_REDIRECT_DELETE = """
mutation RedirectDelete($ids: [ID!]!) {
  urlRedirectBulkDeleteByIds(ids: $ids) {
    deletedCount
    userErrors { field message }
  }
}
"""
