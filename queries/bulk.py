"""
GraphQL query strings for bulk operations.

Note: The main bulk op mutations are in bulk.py (colocated with the manager).
This file has any additional bulk-related queries.
"""

QUERY_CURRENT_BULK_OPERATION = """
query CurrentBulkOperation {
  currentBulkOperation {
    id
    status
    errorCode
    objectCount
    fileSize
    url
    createdAt
    completedAt
    type
  }
}
"""
