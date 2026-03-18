"""GraphQL query and mutation strings for Customers."""

# ─── Customer Queries ─────────────────────────────────────────────────────────

QUERY_CUSTOMER = """
query GetCustomer($id: ID!) {
  customer(id: $id) {
    id
    displayName
    firstName
    lastName
    email
    phone
    state
    note
    tags
    createdAt
    updatedAt
    numberOfOrders
    amountSpent {
      amount
      currencyCode
    }
    taxExempt
    taxExemptions
    emailMarketingConsent {
      marketingState
      consentUpdatedAt
      marketingOptInLevel
    }
    smsMarketingConsent {
      marketingState
      consentUpdatedAt
      marketingOptInLevel
    }
    defaultAddress {
      id
      address1
      address2
      city
      province
      country
      zip
      phone
    }
    addresses {
      id
      address1
      address2
      city
      province
      country
      zip
    }
    orders(first: 10) {
      edges {
        node {
          id
          name
          createdAt
          displayFinancialStatus
          totalPriceSet {
            shopMoney { amount currencyCode }
          }
        }
      }
    }
    metafields(first: 10) {
      edges {
        node {
          namespace
          key
          value
          type
        }
      }
    }
  }
}
"""

QUERY_CUSTOMERS = """
query ListCustomers($first: Int!, $after: String, $query: String) {
  customers(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        displayName
        firstName
        lastName
        email
        phone
        state
        numberOfOrders
        amountSpent {
          amount
          currencyCode
        }
        tags
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

# ─── Customer Mutations ───────────────────────────────────────────────────────

MUTATION_CUSTOMER_CREATE = """
mutation CustomerCreate($input: CustomerInput!) {
  customerCreate(input: $input) {
    customer {
      id
      displayName
      email
      phone
      state
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_CUSTOMER_UPDATE = """
mutation CustomerUpdate($input: CustomerInput!) {
  customerUpdate(input: $input) {
    customer {
      id
      displayName
      email
      phone
      state
      note
      tags
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_CUSTOMER_DELETE = """
mutation CustomerDelete($input: CustomerDeleteInput!) {
  customerDelete(input: $input) {
    deletedCustomerId
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_CUSTOMER_MERGE = """
mutation CustomerMerge($customerOneId: ID!, $customerTwoId: ID!, $customerOneOverrides: CustomerMergeOverrideFields) {
  customerMerge(customerOneId: $customerOneId, customerTwoId: $customerTwoId, customerOneOverrides: $customerOneOverrides) {
    resultingCustomerId
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_CUSTOMER_EMAIL_MARKETING = """
mutation CustomerEmailMarketingConsentUpdate($input: CustomerEmailMarketingConsentUpdateInput!) {
  customerEmailMarketingConsentUpdate(input: $input) {
    customer {
      id
      emailMarketingConsent {
        marketingState
        consentUpdatedAt
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_CUSTOMER_SMS_MARKETING = """
mutation CustomerSmsMarketingConsentUpdate($input: CustomerSmsMarketingConsentUpdateInput!) {
  customerSmsMarketingConsentUpdate(input: $input) {
    customer {
      id
      smsMarketingConsent {
        marketingState
        consentUpdatedAt
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Customer Segments ────────────────────────────────────────────────────────

QUERY_SEGMENTS = """
query ListSegments($first: Int!, $after: String) {
  segments(first: $first, after: $after) {
    edges {
      node {
        id
        name
        query
        creationDate
        lastEditDate
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""
