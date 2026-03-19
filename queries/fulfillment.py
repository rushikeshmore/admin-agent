"""GraphQL query and mutation strings for Fulfillment, Shipping, and Returns."""

QUERY_FULFILLMENT_ORDERS = """
query GetFulfillmentOrders($orderId: ID!) {
  order(id: $orderId) {
    id
    name
    fulfillmentOrders(first: 20) {
      edges {
        node {
          id
          status
          requestStatus
          assignedLocation {
            name
          }
          lineItems(first: 50) {
            edges {
              node {
                id
                totalQuantity
                remainingQuantity
                lineItem {
                  title
                  sku
                }
              }
            }
          }
          deliveryMethod {
            methodType
          }
        }
      }
    }
  }
}
"""

MUTATION_FULFILLMENT_CREATE = """
mutation FulfillmentCreate($fulfillment: FulfillmentV2Input!) {
  fulfillmentCreate(fulfillment: $fulfillment) {
    fulfillment {
      id
      status
      trackingInfo {
        number
        url
        company
      }
      createdAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_FULFILLMENT_CANCEL = """
mutation FulfillmentCancel($id: ID!) {
  fulfillmentCancel(id: $id) {
    fulfillment {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_FULFILLMENT_UPDATE_TRACKING = """
mutation FulfillmentTrackingUpdate($fulfillmentId: ID!, $trackingInfoInput: FulfillmentTrackingInput!) {
  fulfillmentTrackingInfoUpdateV2(fulfillmentId: $fulfillmentId, trackingInfoInput: $trackingInfoInput) {
    fulfillment {
      id
      status
      trackingInfo {
        number
        url
        company
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_FULFILLMENT_ORDER_HOLD = """
mutation FulfillmentOrderHold($fulfillmentHold: FulfillmentOrderHoldInput!, $id: ID!) {
  fulfillmentOrderHold(fulfillmentHold: $fulfillmentHold, id: $id) {
    fulfillmentOrder {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_FULFILLMENT_ORDER_RELEASE = """
mutation FulfillmentOrderRelease($id: ID!) {
  fulfillmentOrderReleaseHold(id: $id) {
    fulfillmentOrder {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_RETURN_CREATE = """
mutation ReturnCreate($input: ReturnInput!) {
  returnCreate(input: $input) {
    return {
      id
      status
      name
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_RETURN_CLOSE = """
mutation ReturnClose($id: ID!) {
  returnClose(id: $id) {
    return {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

QUERY_DELIVERY_PROFILES = """
query ListDeliveryProfiles($first: Int!) {
  deliveryProfiles(first: $first) {
    edges {
      node {
        id
        name
        default
        profileLocationGroups {
          locationGroup {
            locations(first: 10) {
              edges {
                node { id name }
              }
            }
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
