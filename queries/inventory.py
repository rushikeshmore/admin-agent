"""
GraphQL query and mutation strings for Inventory & Locations.
"""

QUERY_INVENTORY_LEVELS = """
query GetInventoryLevels($inventoryItemId: ID!) {
  inventoryItem(id: $inventoryItemId) {
    id
    tracked
    sku
    inventoryLevels(first: 50) {
      edges {
        node {
          id
          quantities(names: ["available", "committed", "damaged", "incoming", "on_hand", "quality_control", "reserved", "safety_stock"]) {
            name
            quantity
          }
          location {
            id
            name
          }
        }
      }
    }
  }
}
"""

QUERY_PRODUCT_INVENTORY = """
query GetProductInventory($id: ID!) {
  product(id: $id) {
    id
    title
    totalInventory
    tracksInventory
    variants(first: 100) {
      edges {
        node {
          id
          title
          sku
          inventoryQuantity
          inventoryItem {
            id
            tracked
            inventoryLevels(first: 10) {
              edges {
                node {
                  quantities(names: ["available", "on_hand", "committed"]) {
                    name
                    quantity
                  }
                  location {
                    id
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

MUTATION_INVENTORY_ADJUST = """
mutation InventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      reason
      changes {
        name
        delta
        quantityAfterChange
        location { name }
        item { id sku }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_INVENTORY_SET = """
mutation InventorySetQuantities($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup {
      reason
      changes {
        name
        delta
        quantityAfterChange
        location { name }
        item { id sku }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_INVENTORY_ACTIVATE = """
mutation InventoryActivate($inventoryItemId: ID!, $locationId: ID!) {
  inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
    inventoryLevel {
      id
      quantities(names: ["available"]) {
        name
        quantity
      }
      location { id name }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_INVENTORY_DEACTIVATE = """
mutation InventoryDeactivate($inventoryLevelId: ID!) {
  inventoryDeactivate(inventoryLevelId: $inventoryLevelId) {
    userErrors {
      field
      message
    }
  }
}
"""

QUERY_LOCATION = """
query GetLocation($id: ID!) {
  location(id: $id) {
    id
    name
    isActive
    fulfillsOnlineOrders
    address {
      address1
      city
      province
      country
      zip
    }
    inventoryLevelsCount
  }
}
"""

QUERY_LOCATIONS = """
query ListLocations($first: Int!, $after: String) {
  locations(first: $first, after: $after) {
    edges {
      node {
        id
        name
        isActive
        fulfillsOnlineOrders
        address {
          address1
          city
          province
          country
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
