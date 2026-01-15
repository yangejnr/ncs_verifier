using System.Text.Json.Serialization;

namespace NcsGateway.Models;

public record ReferenceRead(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("doc_type")] string DocType,
    [property: JsonPropertyName("version")] string Version,
    [property: JsonPropertyName("metadata")] Dictionary<string, object> Metadata,
    [property: JsonPropertyName("created_at")] DateTime CreatedAt
);

public record ReferenceList(
    [property: JsonPropertyName("items")] List<ReferenceRead> Items
);
