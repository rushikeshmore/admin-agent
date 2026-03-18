"""
GraphQL query and mutation strings for Discounts.
"""

QUERY_DISCOUNT = """
query GetDiscount($id: ID!) {
  discountNode(id: $id) {
    id
    discount {
      __typename
      ... on DiscountCodeBasic {
        title
        status
        startsAt
        endsAt
        usageLimit
        asyncUsageCount
        codes(first: 10) {
          edges { node { code } }
        }
        customerGets {
          value {
            ... on DiscountPercentage { percentage }
            ... on DiscountAmount { amount { amount currencyCode } }
          }
        }
        customerSelection {
          ... on DiscountCustomerAll { allCustomers }
        }
        minimumRequirement {
          ... on DiscountMinimumSubtotal { greaterThanOrEqualToSubtotal { amount } }
          ... on DiscountMinimumQuantity { greaterThanOrEqualToQuantity }
        }
        combinesWith { orderDiscounts productDiscounts shippingDiscounts }
      }
      ... on DiscountCodeFreeShipping {
        title
        status
        startsAt
        endsAt
        usageLimit
        asyncUsageCount
        codes(first: 10) {
          edges { node { code } }
        }
        combinesWith { orderDiscounts productDiscounts shippingDiscounts }
      }
      ... on DiscountAutomaticBasic {
        title
        status
        startsAt
        endsAt
        asyncUsageCount
        customerGets {
          value {
            ... on DiscountPercentage { percentage }
            ... on DiscountAmount { amount { amount currencyCode } }
          }
        }
        combinesWith { orderDiscounts productDiscounts shippingDiscounts }
      }
      ... on DiscountAutomaticFreeShipping {
        title
        status
        startsAt
        endsAt
        combinesWith { orderDiscounts productDiscounts shippingDiscounts }
      }
    }
  }
}
"""

QUERY_DISCOUNTS = """
query ListDiscounts($first: Int!, $after: String, $query: String) {
  discountNodes(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        discount {
          __typename
          ... on DiscountCodeBasic {
            title
            status
            startsAt
            endsAt
            asyncUsageCount
          }
          ... on DiscountCodeFreeShipping {
            title
            status
            startsAt
            endsAt
            asyncUsageCount
          }
          ... on DiscountAutomaticBasic {
            title
            status
            startsAt
            endsAt
            asyncUsageCount
          }
          ... on DiscountAutomaticFreeShipping {
            title
            status
            startsAt
            endsAt
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

MUTATION_DISCOUNT_CODE_BASIC_CREATE = """
mutation DiscountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
    codeDiscountNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic {
          title
          status
          codes(first: 1) { edges { node { code } } }
        }
      }
    }
    userErrors { field code message }
  }
}
"""

MUTATION_DISCOUNT_AUTOMATIC_BASIC_CREATE = """
mutation DiscountAutomaticBasicCreate($automaticBasicDiscount: DiscountAutomaticBasicInput!) {
  discountAutomaticBasicCreate(automaticBasicDiscount: $automaticBasicDiscount) {
    automaticDiscountNode {
      id
      automaticDiscount {
        ... on DiscountAutomaticBasic {
          title
          status
          startsAt
        }
      }
    }
    userErrors { field code message }
  }
}
"""

MUTATION_DISCOUNT_CODE_ACTIVATE = """
mutation DiscountCodeActivate($id: ID!) {
  discountCodeActivate(id: $id) {
    codeDiscountNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic { title status }
        ... on DiscountCodeFreeShipping { title status }
      }
    }
    userErrors { field message }
  }
}
"""

MUTATION_DISCOUNT_CODE_DEACTIVATE = """
mutation DiscountCodeDeactivate($id: ID!) {
  discountCodeDeactivate(id: $id) {
    codeDiscountNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic { title status }
        ... on DiscountCodeFreeShipping { title status }
      }
    }
    userErrors { field message }
  }
}
"""

MUTATION_DISCOUNT_AUTOMATIC_ACTIVATE = """
mutation DiscountAutomaticActivate($id: ID!) {
  discountAutomaticActivate(id: $id) {
    automaticDiscountNode {
      id
      automaticDiscount {
        ... on DiscountAutomaticBasic { title status }
        ... on DiscountAutomaticFreeShipping { title status }
      }
    }
    userErrors { field message }
  }
}
"""

MUTATION_DISCOUNT_AUTOMATIC_DEACTIVATE = """
mutation DiscountAutomaticDeactivate($id: ID!) {
  discountAutomaticDeactivate(id: $id) {
    automaticDiscountNode {
      id
      automaticDiscount {
        ... on DiscountAutomaticBasic { title status }
        ... on DiscountAutomaticFreeShipping { title status }
      }
    }
    userErrors { field message }
  }
}
"""

MUTATION_DISCOUNT_DELETE = """
mutation DiscountNodeDelete($id: ID!) {
  discountCodeDelete(id: $id) {
    deletedCodeDiscountId
    userErrors { field message }
  }
}
"""

MUTATION_DISCOUNT_AUTOMATIC_DELETE = """
mutation DiscountAutomaticDelete($id: ID!) {
  discountAutomaticDelete(id: $id) {
    deletedAutomaticDiscountId
    userErrors { field message }
  }
}
"""
