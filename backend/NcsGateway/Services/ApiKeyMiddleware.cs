using System.Text.Json;
using Microsoft.Extensions.Options;
using NcsGateway.Models;

namespace NcsGateway.Services;

public class ApiKeyMiddleware
{
    private readonly RequestDelegate _next;
    private readonly GatewayOptions _options;

    public ApiKeyMiddleware(RequestDelegate next, IOptions<GatewayOptions> options)
    {
        _next = next;
        _options = options.Value;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        if (context.Request.Path.StartsWithSegments("/swagger"))
        {
            await _next(context);
            return;
        }

        var provided = context.Request.Headers["X-Api-Key"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(provided))
        {
            var authHeader = context.Request.Headers["Authorization"].FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(authHeader) && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
            {
                provided = authHeader[7..].Trim();
            }
        }

        if (string.IsNullOrWhiteSpace(_options.ApiKey) || provided == _options.ApiKey)
        {
            await _next(context);
            return;
        }

        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        context.Response.ContentType = "application/json";
        var payload = JsonSerializer.Serialize(new { error = "Unauthorized" });
        await context.Response.WriteAsync(payload);
    }
}
