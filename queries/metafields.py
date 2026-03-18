"""
GraphQL query and mutation strings for Metafields & Metaobjects.
"""

QUERY_METAFIELDS = """
query GetMetafields($ownerId: ID!, $first: Int!, $after: String, $namespace: String) {
  node(id: $ownerId) {
    ... on HasMetafields {
      metafields(first: $first, after: $after, namespace: $namespace) {
        edges {
          node {
            id
            namespace
            key
            value
            type
            createdAt
            updatedAt
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

MUTATION_METAFIELDS_SET = """
mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      id
      namespace
      key
      value
      type
    }
    userErrors { field message }
  }
}
"""

MUTATION_METAFIELDS_DELETE = """
mutation MetafieldDelete($input: MetafieldDeleteInput!) {
  metafieldDelete(input: $input) {
    deletedId
    userErrors { field message }
  }
}
"""

QUERY_METAFIELD_DEFINITIONS = """
query ListMetafieldDefinitions($ownerType: MetafieldOwnerType!, $first: Int!, $after: String) {
  metafieldDefinitions(ownerType: $ownerType, first: $first, after: $after) {
    edges {
      node {
        id
        name
        namespace
        key
        type { name }
        description
        pinnedPosition
        validations { name value }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

QUERY_METAOBJECTS = """
query ListMetaobjects($type: String!, $first: Int!, $after: String) {
  metaobjects(type: $type, first: $first, after: $after) {
    edges {
      node {
        id
        handle
        type
        displayName
        fields {
          key
          value
          type
        }
        updatedAt
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

QUERY_METAOBJECT = """
query GetMetaobject($id: ID!) {
  metaobject(id: $id) {
    id
    handle
    type
    displayName
    fields {
      key
      value
      type
    }
    createdAt
    updatedAt
  }
}
"""

MUTATION_METAOBJECT_CREATE = """
mutation MetaobjectCreate($metaobject: MetaobjectCreateInput!) {
  metaobjectCreate(metaobject: $metaobject) {
    metaobject {
      id
      handle
      type
      displayName
    }
    userErrors { field message }
  }
}
"""

MUTATION_METAOBJECT_UPDATE = """
mutation MetaobjectUpdate($id: ID!, $metaobject: MetaobjectUpdateInput!) {
  metaobjectUpdate(id: $id, metaobject: $metaobject) {
    metaobject {
      id
      handle
      displayName
      updatedAt
    }
    userErrors { field message }
  }
}
"""

MUTATION_METAOBJECT_DELETE = """
mutation MetaobjectDelete($id: ID!) {
  metaobjectDelete(id: $id) {
    deletedId
    userErrors { field message }
  }
}
"""
