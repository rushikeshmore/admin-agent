"""
GraphQL query and mutation strings for Products & Collections.

All constants named QUERY_* or MUTATION_*. Kept separate for readability.
"""

# ─── Product Queries ─────────────────────────────────────────────────────────

QUERY_PRODUCT = """
query GetProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    descriptionHtml
    status
    productType
    vendor
    tags
    createdAt
    updatedAt
    publishedAt
    totalInventory
    tracksInventory
    seo {
      title
      description
    }
    options {
      id
      name
      position
      values
    }
    variants(first: 100) {
      edges {
        node {
          id
          title
          sku
          barcode
          price
          compareAtPrice
          inventoryQuantity
          weight
          weightUnit
          selectedOptions {
            name
            value
          }
        }
      }
    }
    images(first: 20) {
      edges {
        node {
          id
          url
          altText
          width
          height
        }
      }
    }
  }
}
"""

QUERY_PRODUCTS = """
query ListProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        title
        handle
        status
        productType
        vendor
        tags
        totalInventory
        createdAt
        updatedAt
        variants(first: 3) {
          edges {
            node {
              id
              title
              price
              sku
              inventoryQuantity
            }
          }
        }
        featuredImage {
          url
          altText
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

# ─── Product Mutations ────────────────────────────────────────────────────────

MUTATION_PRODUCT_CREATE = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      variants(first: 10) {
        edges {
          node {
            id
            title
            price
            sku
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_PRODUCT_UPDATE = """
mutation ProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      updatedAt
      variants(first: 10) {
        edges {
          node {
            id
            title
            price
            sku
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_PRODUCT_DELETE = """
mutation ProductDelete($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_PRODUCT_DUPLICATE = """
mutation ProductDuplicate($productId: ID!, $newTitle: String!) {
  productDuplicate(productId: $productId, newTitle: $newTitle) {
    newProduct {
      id
      title
      handle
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Variant Mutations ────────────────────────────────────────────────────────

MUTATION_VARIANTS_BULK_CREATE = """
mutation ProductVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    productVariants {
      id
      title
      price
      sku
      inventoryQuantity
      selectedOptions {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_VARIANTS_BULK_UPDATE = """
mutation ProductVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      title
      price
      sku
      selectedOptions {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_VARIANTS_BULK_DELETE = """
mutation ProductVariantsBulkDelete($productId: ID!, $variantsIds: [ID!]!) {
  productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
    product {
      id
      title
    }
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Collection Queries ───────────────────────────────────────────────────────

QUERY_COLLECTION = """
query GetCollection($id: ID!) {
  collection(id: $id) {
    id
    title
    handle
    descriptionHtml
    sortOrder
    ruleSet {
      appliedDisjunctively
      rules {
        column
        relation
        condition
      }
    }
    productsCount {
      count
    }
    products(first: 20) {
      edges {
        node {
          id
          title
          handle
          status
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
    seo {
      title
      description
    }
    image {
      url
      altText
    }
    updatedAt
  }
}
"""

QUERY_COLLECTIONS = """
query ListCollections($first: Int!, $after: String, $query: String) {
  collections(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        title
        handle
        sortOrder
        productsCount {
          count
        }
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

# ─── Collection Mutations ─────────────────────────────────────────────────────

MUTATION_COLLECTION_CREATE = """
mutation CollectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      title
      handle
      sortOrder
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_COLLECTION_UPDATE = """
mutation CollectionUpdate($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      handle
      sortOrder
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_COLLECTION_DELETE = """
mutation CollectionDelete($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) {
    deletedCollectionId
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_COLLECTION_ADD_PRODUCTS = """
mutation CollectionAddProducts($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
      title
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

MUTATION_COLLECTION_REMOVE_PRODUCTS = """
mutation CollectionRemoveProducts($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) {
    userErrors {
      field
      message
    }
  }
}
"""
