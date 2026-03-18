"""
GraphQL query and mutation strings for Orders, Draft Orders, and Abandoned Checkouts.
"""

# ─── Order Queries ────────────────────────────────────────────────────────────

QUERY_ORDER = """
query GetOrder($id: ID!) {
  order(id: $id) {
    id
    name
    createdAt
    updatedAt
    displayFinancialStatus
    displayFulfillmentStatus
    cancelledAt
    cancelReason
    closed
    confirmed
    email
    phone
    note
    tags
    totalPriceSet {
      shopMoney { amount currencyCode }
    }
    subtotalPriceSet {
      shopMoney { amount currencyCode }
    }
    totalShippingPriceSet {
      shopMoney { amount currencyCode }
    }
    totalTaxSet {
      shopMoney { amount currencyCode }
    }
    totalDiscountsSet {
      shopMoney { amount currencyCode }
    }
    totalRefundedSet {
      shopMoney { amount currencyCode }
    }
    currentTotalPriceSet {
      shopMoney { amount currencyCode }
    }
    customer {
      id
      displayName
      email
    }
    shippingAddress {
      address1
      address2
      city
      province
      country
      zip
    }
    lineItems(first: 50) {
      edges {
        node {
          id
          title
          quantity
          sku
          originalUnitPriceSet {
            shopMoney { amount currencyCode }
          }
          discountedUnitPriceSet {
            shopMoney { amount currencyCode }
          }
          variant {
            id
            title
          }
          product {
            id
          }
        }
      }
    }
    fulfillments {
      id
      status
      trackingInfo {
        number
        url
        company
      }
      createdAt
    }
    transactions(first: 10) {
      id
      kind
      status
      amountSet {
        shopMoney { amount currencyCode }
      }
      gateway
      createdAt
    }
    refunds {
      id
      createdAt
      note
      totalRefundedSet {
        shopMoney { amount currencyCode }
      }
    }
    riskLevel
    discountCode
  }
}
"""

QUERY_ORDERS = """
query ListOrders($first: Int!, $after: String, $query: String, $sortKey: OrderSortKeys, $reverse: Boolean) {
  orders(first: $first, after: $after, query: $query, sortKey: $sortKey, reverse: $reverse) {
    edges {
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        cancelledAt
        closed
        totalPriceSet {
          shopMoney { amount currencyCode }
        }
        customer {
          id
          displayName
          email
        }
        lineItems(first: 5) {
          edges {
            node {
              title
              quantity
              sku
            }
          }
        }
        tags
        riskLevel
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# ─── Order Mutations ──────────────────────────────────────────────────────────

MUTATION_ORDER_UPDATE = """
mutation OrderUpdate($input: OrderInput!) {
  orderUpdate(input: $input) {
    order {
      id
      name
      note
      tags
      email
      phone
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_ORDER_CANCEL = """
mutation OrderCancel($orderId: ID!, $reason: OrderCancelReason!, $notifyCustomer: Boolean, $refund: Boolean, $restock: Boolean) {
  orderCancel(orderId: $orderId, reason: $reason, notifyCustomer: $notifyCustomer, refund: $refund, restock: $restock) {
    orderCancelUserErrors {
      field
      message
    }
  }
}
"""

MUTATION_ORDER_CLOSE = """
mutation OrderClose($input: OrderCloseInput!) {
  orderClose(input: $input) {
    order {
      id
      name
      closed
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_ORDER_OPEN = """
mutation OrderOpen($input: OrderOpenInput!) {
  orderOpen(input: $input) {
    order {
      id
      name
      closed
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_ORDER_CAPTURE = """
mutation OrderCapture($input: OrderCaptureInput!) {
  orderCapture(input: $input) {
    transaction {
      id
      kind
      status
      amountSet {
        shopMoney { amount currencyCode }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_REFUND_CREATE = """
mutation RefundCreate($input: RefundInput!) {
  refundCreate(input: $input) {
    refund {
      id
      createdAt
      totalRefundedSet {
        shopMoney { amount currencyCode }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_ORDER_MARK_AS_PAID = """
mutation OrderMarkAsPaid($input: OrderMarkAsPaidInput!) {
  orderMarkAsPaid(input: $input) {
    order {
      id
      name
      displayFinancialStatus
    }
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Draft Order Queries & Mutations ──────────────────────────────────────────

QUERY_DRAFT_ORDER = """
query GetDraftOrder($id: ID!) {
  draftOrder(id: $id) {
    id
    name
    status
    createdAt
    updatedAt
    email
    note2
    tags
    totalPriceSet {
      shopMoney { amount currencyCode }
    }
    subtotalPriceSet {
      shopMoney { amount currencyCode }
    }
    totalTaxSet {
      shopMoney { amount currencyCode }
    }
    customer {
      id
      displayName
      email
    }
    lineItems(first: 50) {
      edges {
        node {
          id
          title
          quantity
          originalUnitPriceSet {
            shopMoney { amount currencyCode }
          }
          variant {
            id
            title
          }
          product {
            id
          }
        }
      }
    }
    shippingAddress {
      address1
      city
      province
      country
      zip
    }
    order {
      id
      name
    }
  }
}
"""

QUERY_DRAFT_ORDERS = """
query ListDraftOrders($first: Int!, $after: String, $query: String) {
  draftOrders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        status
        createdAt
        totalPriceSet {
          shopMoney { amount currencyCode }
        }
        customer {
          id
          displayName
          email
        }
        order {
          id
          name
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

MUTATION_DRAFT_ORDER_CREATE = """
mutation DraftOrderCreate($input: DraftOrderInput!) {
  draftOrderCreate(input: $input) {
    draftOrder {
      id
      name
      status
      totalPriceSet {
        shopMoney { amount currencyCode }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_DRAFT_ORDER_COMPLETE = """
mutation DraftOrderComplete($id: ID!, $paymentPending: Boolean) {
  draftOrderComplete(id: $id, paymentPending: $paymentPending) {
    draftOrder {
      id
      name
      status
      order {
        id
        name
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_DRAFT_ORDER_INVOICE_SEND = """
mutation DraftOrderInvoiceSend($id: ID!, $email: DraftOrderInvoiceInput) {
  draftOrderInvoiceSend(id: $id, email: $email) {
    draftOrder {
      id
      name
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_DRAFT_ORDER_DELETE = """
mutation DraftOrderDelete($input: DraftOrderDeleteInput!) {
  draftOrderDelete(input: $input) {
    deletedId
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Abandoned Checkouts ─────────────────────────────────────────────────────

QUERY_ABANDONED_CHECKOUTS = """
query ListAbandonedCheckouts($first: Int!, $after: String, $query: String) {
  abandonedCheckouts(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        createdAt
        updatedAt
        abandonedCheckoutUrl
        totalPriceSet {
          shopMoney { amount currencyCode }
        }
        customer {
          id
          displayName
          email
        }
        lineItems(first: 10) {
          edges {
            node {
              title
              quantity
              variant {
                id
                title
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
