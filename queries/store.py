"""
GraphQL query strings for Store settings, Themes, Files, and read-only resources.
"""

QUERY_SHOP = """
query GetShop {
  shop {
    id
    name
    email
    myshopifyDomain
    primaryDomain { url host }
    plan { displayName partnerDevelopment shopifyPlus }
    currencyCode
    weightUnit
    timezoneAbbreviation
    ianaTimezone
    countriesInShippingZones { countryCodes }
    taxesIncluded
    billingAddress {
      address1
      city
      province
      country
      zip
    }
    createdAt
    updatedAt
  }
}
"""

QUERY_THEMES = """
query ListThemes($first: Int!) {
  themes(first: $first) {
    edges {
      node {
        id
        name
        role
        createdAt
        updatedAt
      }
    }
  }
}
"""

QUERY_FILES = """
query ListFiles($first: Int!, $after: String, $query: String) {
  files(first: $first, after: $after, query: $query) {
    edges {
      node {
        ... on MediaImage {
          id
          alt
          mimeType
          image { url width height }
          createdAt
        }
        ... on Video {
          id
          alt
          createdAt
        }
        ... on GenericFile {
          id
          alt
          mimeType
          url
          createdAt
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

QUERY_PUBLICATIONS = """
query ListPublications($first: Int!) {
  publications(first: $first) {
    edges {
      node {
        id
        name
        supportsFuturePublishing
        app { title }
      }
    }
  }
}
"""

MUTATION_PUBLISH_RESOURCE = """
mutation PublishablePublish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable {
      availablePublicationsCount { count }
    }
    userErrors { field message }
  }
}
"""

MUTATION_UNPUBLISH_RESOURCE = """
mutation PublishableUnpublish($id: ID!, $input: [PublicationInput!]!) {
  publishableUnpublish(id: $id, input: $input) {
    publishable {
      availablePublicationsCount { count }
    }
    userErrors { field message }
  }
}
"""

QUERY_PAYOUTS = """
query ListPayouts($first: Int!, $after: String) {
  shopifyPaymentsAccount {
    payouts(first: $first, after: $after) {
      edges {
        node {
          id
          status
          net { amount currencyCode }
          gross { amount currencyCode }
          fee { amount currencyCode }
          issuedAt
          transactionType
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
