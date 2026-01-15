namespace NcsGateway.Models;

public class GatewayOptions
{
    public string PythonVerifierUrl { get; set; } = "http://127.0.0.1:9001";
    public string ApiKey { get; set; } = "dev-key";
    public string DataPath { get; set; } = "Data/gateway.db";
}
