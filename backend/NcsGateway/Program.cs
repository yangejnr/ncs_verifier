using System.Text.Json;
using Microsoft.Extensions.Options;
using NcsGateway.Models;
using NcsGateway.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyHeader().AllowAnyMethod().AllowAnyOrigin());
});

builder.Services.Configure<GatewayOptions>(builder.Configuration.GetSection("Gateway"));

builder.Services.AddSingleton(sp =>
{
    var options = sp.GetRequiredService<IOptions<GatewayOptions>>().Value;
    return new SqliteStore(options.DataPath);
});

builder.Services.AddHttpClient<VerifierClient>((sp, client) =>
{
    var options = sp.GetRequiredService<IOptions<GatewayOptions>>().Value;
    client.BaseAddress = new Uri(options.PythonVerifierUrl);
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseCors();
app.UseMiddleware<ApiKeyMiddleware>();

var jsonOptions = new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

app.MapPost("/v1/sessions", (SessionCreate payload, SqliteStore store, ILogger<Program> logger) =>
{
    var sessionId = Guid.NewGuid().ToString();
    var record = new SessionRecord(sessionId, payload.DocType, "queued", 0, null, null, DateTime.UtcNow);
    store.CreateSession(record);
    store.AddAuditLog(Guid.NewGuid().ToString(), sessionId, "session_created", JsonSerializer.Serialize(payload, jsonOptions));

    logger.LogInformation("session_created {SessionId}", sessionId);
    return Results.Json(new SessionRead(sessionId, record.CreatedAt, record.DocType));
});

app.MapGet("/v1/sessions/{sessionId}/status", (string sessionId, SqliteStore store) =>
{
    var session = store.GetSession(sessionId);
    if (session == null)
    {
        return Results.NotFound(new { error = "Session not found" });
    }

    return Results.Json(new SessionStatus(session.Id, session.Stage, session.Percent, session.Message));
});

app.MapGet("/v1/sessions/{sessionId}/result", (string sessionId, SqliteStore store) =>
{
    var session = store.GetSession(sessionId);
    if (session == null)
    {
        return Results.NotFound(new { error = "Session not found" });
    }

    if (string.IsNullOrWhiteSpace(session.ResultJson))
    {
        return Results.NotFound(new { error = "Result not ready" });
    }

    return Results.Text(session.ResultJson, "application/json");
});

app.MapPost("/v1/sessions/{sessionId}/frame", async (
    string sessionId,
    HttpRequest request,
    SqliteStore store,
    VerifierClient verifier,
    ILogger<Program> logger,
    CancellationToken ct) =>
{
    var session = store.GetSession(sessionId);
    if (session == null)
    {
        return Results.NotFound(new { error = "Session not found" });
    }

    if (!request.HasFormContentType)
    {
        return Results.BadRequest(new { error = "Expected multipart/form-data" });
    }

    var form = await request.ReadFormAsync(ct);
    var file = form.Files.GetFile("file");
    if (file == null)
    {
        return Results.BadRequest(new { error = "file is required" });
    }

    var docType = form["doc_type"].FirstOrDefault() ?? session.DocType;
    store.UpdateSessionStatus(sessionId, "verifying", 55, "Sending to verifier");

    try
    {
        await using var stream = file.OpenReadStream();
        var verifyResponse = await verifier.VerifyAsync(stream, file.FileName, docType, ct);
        var resultJson = JsonSerializer.Serialize(verifyResponse.Result, jsonOptions);
        store.UpdateSessionResult(sessionId, resultJson);
        store.AddAuditLog(Guid.NewGuid().ToString(), sessionId, "verification_completed", JsonSerializer.Serialize(verifyResponse, jsonOptions));

        logger.LogInformation("verification_completed {SessionId}", sessionId);
        return Results.Json(verifyResponse);
    }
    catch (Exception ex)
    {
        store.UpdateSessionStatus(sessionId, "error", 100, ex.Message);
        store.AddAuditLog(Guid.NewGuid().ToString(), sessionId, "verification_failed", JsonSerializer.Serialize(new { error = ex.Message }, jsonOptions));
        logger.LogError(ex, "verification_failed {SessionId}", sessionId);
        return Results.Problem("Verification failed", statusCode: 502);
    }
});

app.MapPost("/v1/references", async (
    HttpRequest request,
    VerifierClient verifier,
    CancellationToken ct) =>
{
    if (!request.HasFormContentType)
    {
        return Results.BadRequest(new { error = "Expected multipart/form-data" });
    }

    var form = await request.ReadFormAsync(ct);
    var file = form.Files.GetFile("file");
    var docType = form["doc_type"].FirstOrDefault();
    var version = form["version"].FirstOrDefault();
    var metadata = form["metadata"].FirstOrDefault() ?? "{}";

    if (file == null || string.IsNullOrWhiteSpace(docType) || string.IsNullOrWhiteSpace(version))
    {
        return Results.BadRequest(new { error = "file, doc_type, and version are required" });
    }

    await using var stream = file.OpenReadStream();
    var reference = await verifier.CreateReferenceAsync(stream, file.FileName, docType, version, metadata, ct);
    return Results.Json(reference);
});

app.MapGet("/v1/references", async (VerifierClient verifier, CancellationToken ct) =>
{
    var list = await verifier.ListReferencesAsync(ct);
    return Results.Json(list);
});

app.MapGet("/v1/references/{refId}", async (string refId, VerifierClient verifier, CancellationToken ct) =>
{
    var reference = await verifier.GetReferenceAsync(refId, ct);
    return reference == null ? Results.NotFound(new { error = "Reference not found" }) : Results.Json(reference);
});

app.Run();
