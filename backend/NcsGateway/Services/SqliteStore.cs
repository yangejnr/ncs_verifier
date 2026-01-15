using Microsoft.Data.Sqlite;
using NcsGateway.Models;

namespace NcsGateway.Services;

public class SqliteStore
{
    private readonly string _dbPath;

    public SqliteStore(string dbPath)
    {
        _dbPath = dbPath;
        Directory.CreateDirectory(Path.GetDirectoryName(dbPath) ?? "Data");
        Init();
    }

    private void Init()
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                doc_type TEXT,
                stage TEXT NOT NULL,
                percent INTEGER NOT NULL,
                message TEXT,
                result_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        ";
        cmd.ExecuteNonQuery();
    }

    public void CreateSession(SessionRecord session)
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO sessions (id, doc_type, stage, percent, message, result_json, created_at)
            VALUES ($id, $doc_type, $stage, $percent, $message, $result_json, $created_at);
        ";
        cmd.Parameters.AddWithValue("$id", session.Id);
        cmd.Parameters.AddWithValue("$doc_type", session.DocType ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$stage", session.Stage);
        cmd.Parameters.AddWithValue("$percent", session.Percent);
        cmd.Parameters.AddWithValue("$message", session.Message ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$result_json", session.ResultJson ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$created_at", session.CreatedAt.ToString("O"));
        cmd.ExecuteNonQuery();
    }

    public SessionRecord? GetSession(string sessionId)
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM sessions WHERE id = $id";
        cmd.Parameters.AddWithValue("$id", sessionId);
        using var reader = cmd.ExecuteReader();
        if (!reader.Read())
        {
            return null;
        }

        return new SessionRecord(
            reader.GetString(0),
            reader.IsDBNull(1) ? null : reader.GetString(1),
            reader.GetString(2),
            reader.GetInt32(3),
            reader.IsDBNull(4) ? null : reader.GetString(4),
            reader.IsDBNull(5) ? null : reader.GetString(5),
            DateTime.Parse(reader.GetString(6))
        );
    }

    public void UpdateSessionStatus(string sessionId, string stage, int percent, string? message)
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            UPDATE sessions SET stage = $stage, percent = $percent, message = $message WHERE id = $id;
        ";
        cmd.Parameters.AddWithValue("$id", sessionId);
        cmd.Parameters.AddWithValue("$stage", stage);
        cmd.Parameters.AddWithValue("$percent", percent);
        cmd.Parameters.AddWithValue("$message", message ?? (object)DBNull.Value);
        cmd.ExecuteNonQuery();
    }

    public void UpdateSessionResult(string sessionId, string resultJson)
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            UPDATE sessions SET result_json = $result_json, stage = 'done', percent = 100 WHERE id = $id;
        ";
        cmd.Parameters.AddWithValue("$id", sessionId);
        cmd.Parameters.AddWithValue("$result_json", resultJson);
        cmd.ExecuteNonQuery();
    }

    public void AddAuditLog(string auditId, string sessionId, string eventType, string payloadJson)
    {
        using var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO audit_logs (id, session_id, event_type, payload_json, created_at)
            VALUES ($id, $session_id, $event_type, $payload_json, $created_at);
        ";
        cmd.Parameters.AddWithValue("$id", auditId);
        cmd.Parameters.AddWithValue("$session_id", sessionId);
        cmd.Parameters.AddWithValue("$event_type", eventType);
        cmd.Parameters.AddWithValue("$payload_json", payloadJson);
        cmd.Parameters.AddWithValue("$created_at", DateTime.UtcNow.ToString("O"));
        cmd.ExecuteNonQuery();
    }
}
