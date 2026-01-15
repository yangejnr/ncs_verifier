using System.Net.Http.Headers;
using System.Text.Json;
using NcsGateway.Models;

namespace NcsGateway.Services;

public class VerifierClient
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions;

    public VerifierClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
        _jsonOptions = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
    }

    public async Task<VerifyResponse> VerifyAsync(Stream imageStream, string fileName, string? docType, CancellationToken ct)
    {
        using var content = new MultipartFormDataContent();
        var fileContent = new StreamContent(imageStream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
        content.Add(fileContent, "file", fileName);
        if (!string.IsNullOrWhiteSpace(docType))
        {
            content.Add(new StringContent(docType), "doc_type");
        }

        var response = await _httpClient.PostAsync("/v1/verify", content, ct);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadAsStringAsync(ct);
        var result = JsonSerializer.Deserialize<VerifyResponse>(payload, _jsonOptions);
        if (result == null)
        {
            throw new InvalidOperationException("Verifier response was empty");
        }
        return result;
    }

    public async Task<ReferenceRead> CreateReferenceAsync(Stream imageStream, string fileName, string docType, string version, string metadataJson, CancellationToken ct)
    {
        using var content = new MultipartFormDataContent();
        var fileContent = new StreamContent(imageStream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
        content.Add(fileContent, "file", fileName);
        content.Add(new StringContent(docType), "doc_type");
        content.Add(new StringContent(version), "version");
        content.Add(new StringContent(metadataJson), "metadata");

        var response = await _httpClient.PostAsync("/v1/references", content, ct);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadAsStringAsync(ct);
        var result = JsonSerializer.Deserialize<ReferenceRead>(payload, _jsonOptions);
        if (result == null)
        {
            throw new InvalidOperationException("Verifier response was empty");
        }
        return result;
    }

    public async Task<ReferenceList> ListReferencesAsync(CancellationToken ct)
    {
        var response = await _httpClient.GetAsync("/v1/references", ct);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadAsStringAsync(ct);
        var result = JsonSerializer.Deserialize<ReferenceList>(payload, _jsonOptions);
        return result ?? new ReferenceList(new List<ReferenceRead>());
    }

    public async Task<ReferenceRead?> GetReferenceAsync(string refId, CancellationToken ct)
    {
        var response = await _httpClient.GetAsync($"/v1/references/{refId}", ct);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }
        var payload = await response.Content.ReadAsStringAsync(ct);
        return JsonSerializer.Deserialize<ReferenceRead>(payload, _jsonOptions);
    }
}
