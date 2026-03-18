"""
GraphQL query strings for ShopifyQL analytics.
"""

QUERY_SHOPIFYQL = """
query RunShopifyQL($query: String!) {
  shopifyqlQuery(query: $query) {
    __typename
    ... on TableResponse {
      tableData {
        rowData
        columns {
          name
          dataType
        }
      }
    }
    ... on PolarisVizResponse {
      data {
        key
        isComparison
      }
    }
    parseErrors {
      code
      message
      range {
        start { line character }
        end { line character }
      }
    }
  }
}
"""
