using System.Text.Json.Serialization;

namespace NcsGateway.Models;

public record SessionCreate(string? DocType);

public record SessionRead(string Id, DateTime CreatedAt, string? DocType);

public record SessionStatus(string SessionId, string Stage, int Percent, string? Message);

public record SessionRecord(string Id, string? DocType, string Stage, int Percent, string? Message, string? ResultJson, DateTime CreatedAt);

public record Finding(
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("severity")] string Severity,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("bbox")] int[] Bbox,
    [property: JsonPropertyName("score")] float Score
);

public record AnalysisSummary(
    [property: JsonPropertyName("doc_type_guess")] string? DocTypeGuess,
    [property: JsonPropertyName("reference_id")] string? ReferenceId,
    [property: JsonPropertyName("match_score")] float MatchScore,
    [property: JsonPropertyName("tamper_risk_score")] float TamperRiskScore,
    [property: JsonPropertyName("confidence_band")] string ConfidenceBand,
    [property: JsonPropertyName("disclaimer")] string Disclaimer
);

public record QualityMetrics(
    [property: JsonPropertyName("blur_score")] float BlurScore,
    [property: JsonPropertyName("glare_ratio")] float GlareRatio,
    [property: JsonPropertyName("acceptable")] bool Acceptable
);

public record AnalysisMetrics(
    [property: JsonPropertyName("template_match_score")] float TemplateMatchScore,
    [property: JsonPropertyName("ocr_quality_score")] float OcrQualityScore,
    [property: JsonPropertyName("tamper_risk_score")] float TamperRiskScore,
    [property: JsonPropertyName("quality_metrics")] QualityMetrics QualityMetrics
);

public record AnalysisResult(
    [property: JsonPropertyName("summary")] AnalysisSummary Summary,
    [property: JsonPropertyName("metrics")] AnalysisMetrics Metrics,
    [property: JsonPropertyName("extracted_fields")] Dictionary<string, string> ExtractedFields,
    [property: JsonPropertyName("ocr_text")] string OcrText,
    [property: JsonPropertyName("findings")] List<Finding> Findings
);

public record VerifyResponse(
    [property: JsonPropertyName("result")] AnalysisResult Result,
    [property: JsonPropertyName("audit_id")] string AuditId
);
