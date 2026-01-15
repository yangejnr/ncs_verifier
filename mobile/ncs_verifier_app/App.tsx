import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  Image,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Camera, CameraCapturedPicture } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import Constants from "expo-constants";
import jpeg from "jpeg-js";
import { Buffer } from "buffer";

const GATEWAY_URL = process.env.EXPO_PUBLIC_NCS_GATEWAY_URL || Constants.expoConfig?.extra?.gatewayUrl || "http://127.0.0.1:7001";
const DOC_TYPE = process.env.EXPO_PUBLIC_NCS_DOC_TYPE || "NCS_ORIGIN";
const API_KEY = process.env.EXPO_PUBLIC_NCS_API_KEY || "dev-key";
const QUEUE_KEY = "ncs_queue_v1";
const LOGO = require("./assets/branding/ncs_logo.png");

const ADMIN_USERNAME = "admin";
const ADMIN_PASSWORD = "P@ssword1";

type Screen = "login" | "dashboard" | "scan" | "settings" | "history";

type Finding = {
  category: string;
  severity: string;
  message: string;
  bbox: number[];
  score: number;
};

type VerifyResult = {
  matchScore: number;
  tamperRisk: number;
  confidence: string;
  disclaimer: string;
  findings: Finding[];
  imageWidth: number;
  imageHeight: number;
  imageUri: string;
};

type QueuedFrame = {
  id: string;
  uri: string;
  docType: string;
  width: number;
  height: number;
  createdAt: string;
};

type HistoryEntry = {
  id: string;
  timestamp: string;
  matchScore: number;
  tamperRisk: number;
  confidence: string;
  source: string;
};

export default function App() {
  const [permission, requestPermission] = Camera.useCameraPermissions();
  const cameraRef = useRef<Camera | null>(null);
  const [screen, setScreen] = useState<Screen>("login");
  const [username, setUsername] = useState("NCS56288");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState("Hold steady…");
  const [busy, setBusy] = useState(false);
  const [stableCount, setStableCount] = useState(0);
  const [sharpnessScores, setSharpnessScores] = useState<number[]>([]);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    if (!permission) {
      return;
    }
    if (screen === "scan" && !permission.granted) {
      requestPermission();
    }
  }, [permission, requestPermission, screen]);

  useEffect(() => {
    if (screen !== "scan") {
      setSharpnessScores([]);
      setStableCount(0);
      setBusy(false);
      setStatus("Hold steady…");
      setProgress(0);
    }
  }, [screen]);

  useEffect(() => {
    if (screen !== "scan" || !permission?.granted) {
      return;
    }

    const interval = setInterval(async () => {
      if (busy) {
        return;
      }
      if (!cameraRef.current) {
        return;
      }

      try {
        const snapshot = await capturePreview(cameraRef.current);
        const score = await computeSharpness(snapshot);
        setSharpnessScores((prev) => [...prev, score].slice(-8));

        const newScores = [...sharpnessScores, score].slice(-8);
        if (newScores.length >= 6) {
          const mean = average(newScores);
          const variance = varianceOf(newScores, mean);
          if (variance < 8 && mean > 12) {
            setStableCount((count) => count + 1);
            setStatus("Stable detected… analyzing");
          } else {
            setStableCount(0);
            setStatus("Hold steady…");
          }
        }

        if (stableCount >= 3 && snapshot) {
          setStableCount(0);
          await uploadSnapshot(snapshot);
        }
      } catch (err) {
        setStatus("Camera warmup…");
      }
    }, 550);

    return () => clearInterval(interval);
  }, [busy, permission, sharpnessScores, stableCount, screen]);

  useEffect(() => {
    flushQueue();
  }, []);

  const handleLogin = () => {
    if (username.trim() === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
      setLoginError("");
      setPassword("");
      setScreen("dashboard");
      return;
    }
    setLoginError("Invalid username or password.");
  };

  const handleLogout = () => {
    setScreen("login");
    setUsername("");
    setPassword("");
    setLoginError("");
    setResult(null);
  };

  const handleClose = () => {
    setUsername("");
    setPassword("");
    setLoginError("");
  };

  const capturePreview = async (camera: Camera) => {
    const snapshot = await camera.takePictureAsync({
      quality: 0.4,
      skipProcessing: true,
    });

    const resized = await ImageManipulator.manipulateAsync(
      snapshot.uri,
      [{ resize: { width: 320 } }],
      { compress: 0.6, format: ImageManipulator.SaveFormat.JPEG, base64: true }
    );

    return {
      original: snapshot,
      preview: resized,
    };
  };

  const addHistoryEntry = (matchScore: number, tamperRisk: number, confidence: string, source: string) => {
    const entry: HistoryEntry = {
      id: `${Date.now()}`,
      timestamp: new Date().toISOString(),
      matchScore,
      tamperRisk,
      confidence,
      source,
    };
    setHistory((prev) => [entry, ...prev]);
  };

  const uploadSnapshot = async (snapshot: { original: CameraCapturedPicture; preview: ImageManipulator.ImageResult }) => {
    setBusy(true);
    setProgress(15);
    setStatus("Uploading frame…");
    setResult(null);

    try {
      const session = await fetch(`${GATEWAY_URL}/v1/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Api-Key": API_KEY },
        body: JSON.stringify({ docType: DOC_TYPE }),
      });

      if (!session.ok) {
        throw new Error("Session creation failed");
      }

      const sessionData = await session.json();
      const sessionId = sessionData.id;

      const form = new FormData();
      form.append("doc_type", DOC_TYPE);
      form.append("file", {
        uri: snapshot.original.uri,
        name: "frame.jpg",
        type: "image/jpeg",
      } as unknown as Blob);

      setProgress(55);
      setStatus("Analyzing…");

      const response = await fetch(`${GATEWAY_URL}/v1/sessions/${sessionId}/frame`, {
        method: "POST",
        headers: { "X-Api-Key": API_KEY },
        body: form,
      });

      if (!response.ok) {
        throw new Error("Verification failed");
      }

      const payload = await response.json();
      const resultPayload = payload.result;
      const matchScore = resultPayload.summary.match_score;
      const tamperRisk = resultPayload.summary.tamper_risk_score;
      const confidence = resultPayload.summary.confidence_band;

      setResult({
        matchScore,
        tamperRisk,
        confidence,
        disclaimer: resultPayload.summary.disclaimer,
        findings: resultPayload.findings || [],
        imageWidth: snapshot.original.width || 1,
        imageHeight: snapshot.original.height || 1,
        imageUri: snapshot.original.uri,
      });
      addHistoryEntry(matchScore, tamperRisk, confidence, "live");
      setProgress(100);
      setStatus("Done");
    } catch (err) {
      await queueSnapshot(snapshot.original);
      setStatus("Queued for upload (offline)");
      setProgress(0);
    } finally {
      setBusy(false);
    }
  };

  const queueSnapshot = async (snapshot: CameraCapturedPicture) => {
    const current = await readQueue();
    const next: QueuedFrame = {
      id: `${Date.now()}`,
      uri: snapshot.uri,
      docType: DOC_TYPE,
      width: snapshot.width || 1,
      height: snapshot.height || 1,
      createdAt: new Date().toISOString(),
    };
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify([...current, next]));
  };

  const flushQueue = async () => {
    const queue = await readQueue();
    if (!queue.length) {
      return;
    }

    for (const item of queue) {
      try {
        const session = await fetch(`${GATEWAY_URL}/v1/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Api-Key": API_KEY },
          body: JSON.stringify({ docType: item.docType }),
        });

        if (!session.ok) {
          continue;
        }

        const sessionData = await session.json();
        const sessionId = sessionData.id;
        const form = new FormData();
        form.append("doc_type", item.docType);
        form.append("file", {
          uri: item.uri,
          name: "frame.jpg",
          type: "image/jpeg",
        } as unknown as Blob);

        const response = await fetch(`${GATEWAY_URL}/v1/sessions/${sessionId}/frame`, {
          method: "POST",
          headers: { "X-Api-Key": API_KEY },
          body: form,
        });

        if (response.ok) {
          const payload = await response.json();
          const resultPayload = payload.result;
          const matchScore = resultPayload.summary.match_score;
          const tamperRisk = resultPayload.summary.tamper_risk_score;
          const confidence = resultPayload.summary.confidence_band;

          setResult({
            matchScore,
            tamperRisk,
            confidence,
            disclaimer: resultPayload.summary.disclaimer,
            findings: resultPayload.findings || [],
            imageWidth: item.width,
            imageHeight: item.height,
            imageUri: item.uri,
          });
          addHistoryEntry(matchScore, tamperRisk, confidence, "offline");
          setStatus("Queued frame processed");
          setProgress(100);
        }
      } catch (err) {
        setStatus("Queue retry failed");
      }
    }

    await AsyncStorage.removeItem(QUEUE_KEY);
  };

  const readQueue = async (): Promise<QueuedFrame[]> => {
    const stored = await AsyncStorage.getItem(QUEUE_KEY);
    if (!stored) {
      return [];
    }
    try {
      return JSON.parse(stored) as QueuedFrame[];
    } catch {
      return [];
    }
  };

  const renderHeader = (title: string, subtitle: string, showBack = false) => (
    <View style={styles.header}>
      <View style={styles.logoBadge}>
        <Image source={LOGO} style={styles.logo} resizeMode="contain" />
      </View>
      <View style={styles.headerText}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.subtitle}>{subtitle}</Text>
      </View>
      {showBack && (
        <TouchableOpacity style={styles.backButton} onPress={() => setScreen("dashboard")}>
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  const renderLogin = () => (
    <SafeAreaView style={styles.loginContainer}>
      <View style={styles.loginCard}>
        <View style={styles.loginLogoWrap}>
          <Image source={LOGO} style={styles.loginLogo} resizeMode="contain" />
        </View>
        <Text style={styles.loginTitle}>NCS Verify</Text>
        <Text style={styles.loginSubtitle}>Secure document verification portal</Text>

        <TextInput
          style={styles.input}
          placeholder="Username or Service No"
          placeholderTextColor="#94A3B8"
          autoCapitalize="none"
          value={username}
          onChangeText={setUsername}
        />
        <View style={styles.inputRow}>
          <TextInput
            style={styles.inputFlex}
            placeholder="Password"
            placeholderTextColor="#94A3B8"
            secureTextEntry={!showPassword}
            value={password}
            onChangeText={setPassword}
          />
          <TouchableOpacity style={styles.eyeButton} onPress={() => setShowPassword((prev) => !prev)}>
            <Text style={styles.eyeButtonText}>{showPassword ? "Hide" : "Show"}</Text>
          </TouchableOpacity>
        </View>
        {loginError ? <Text style={styles.errorText}>{loginError}</Text> : null}
        <TouchableOpacity style={styles.primaryButton} onPress={handleLogin}>
          <Text style={styles.primaryButtonText}>Login</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.closeButton} onPress={handleClose}>
          <Text style={styles.closeButtonText}>Close</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );

  const renderDashboard = () => (
    <SafeAreaView style={styles.container}>
      {renderHeader("NCS Verify", "Document Authenticity Scanner")}
      <View style={styles.dashboardPanel}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionGrid}>
          <TouchableOpacity style={styles.actionButton} onPress={() => setScreen("scan")}>
            <Text style={styles.actionText}>New Scan</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => setScreen("history")}>
            <Text style={styles.actionText}>Scan History</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => setScreen("settings")}>
            <Text style={styles.actionText}>Account Settings</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionButton, styles.logoutButton]} onPress={handleLogout}>
            <Text style={styles.logoutText}>Logout</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );

  const renderSettings = () => (
    <SafeAreaView style={styles.container}>
      {renderHeader("Account Settings", "Manage your access", true)}
      <View style={styles.contentCard}>
        <Text style={styles.sectionTitle}>Profile</Text>
        <Text style={styles.resultLine}>Signed in as: {ADMIN_USERNAME}</Text>
        <Text style={styles.disclaimer}>Credential management will be integrated with enterprise SSO.</Text>
      </View>
    </SafeAreaView>
  );

  const renderHistory = () => (
    <SafeAreaView style={styles.container}>
      {renderHeader("Scan History", "Recent verification sessions", true)}
      <ScrollView contentContainerStyle={styles.historyList}>
        {history.length === 0 ? (
          <Text style={styles.resultPlaceholder}>No scans yet.</Text>
        ) : (
          history.map((entry) => (
            <View key={entry.id} style={styles.historyCard}>
              <Text style={styles.historyTitle}>Session {entry.id}</Text>
              <Text style={styles.historyMeta}>Time: {new Date(entry.timestamp).toLocaleString()}</Text>
              <Text style={styles.historyMeta}>Source: {entry.source}</Text>
              <Text style={styles.historyMeta}>Match: {entry.matchScore.toFixed(1)}% | Risk: {entry.tamperRisk.toFixed(1)}%</Text>
              <Text style={styles.historyMeta}>Confidence: {entry.confidence}</Text>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );

  const renderScan = () => {
    if (!permission) {
      return (
        <SafeAreaView style={styles.center}>
          <Text style={styles.permissionText}>Requesting camera permission…</Text>
        </SafeAreaView>
      );
    }

    if (!permission.granted) {
      return (
        <SafeAreaView style={styles.center}>
          <Text style={styles.permissionText}>Camera access is required.</Text>
          <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
            <Text style={styles.primaryButtonText}>Grant Permission</Text>
          </TouchableOpacity>
        </SafeAreaView>
      );
    }

    return (
      <SafeAreaView style={styles.container}>
        {renderHeader("New Scan", "Align the document inside the frame", true)}
        <View style={styles.cameraFrame}>
          <Camera ref={cameraRef} style={styles.camera} ratio="16:9" />
          <View style={styles.overlay}>
            <Text style={styles.overlayText}>{status}</Text>
            {busy && <ActivityIndicator size="small" color="#fff" />}
          </View>
        </View>

        <View style={styles.panel}>
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: `${progress}%` }]} />
          </View>

          {result ? (
            <View>
              <Text style={styles.resultTitle}>Result</Text>
              <Text style={styles.resultLine}>Template match: {result.matchScore.toFixed(1)}%</Text>
              <Text style={styles.resultLine}>Tamper risk: {result.tamperRisk.toFixed(1)}%</Text>
              <Text style={styles.resultLine}>Confidence: {result.confidence}</Text>
              <Text style={styles.disclaimer}>{result.disclaimer}</Text>

              <View style={styles.previewContainer}>
                <Image source={{ uri: result.imageUri }} style={styles.previewImage} />
                {result.findings.slice(0, 6).map((finding, index) => (
                  <View key={`${finding.category}-${index}`} style={mapFindingBox(finding.bbox, result.imageWidth, result.imageHeight)} />
                ))}
              </View>

              {result.findings.slice(0, 6).map((finding, index) => (
                <Text key={`${finding.category}-${index}`} style={styles.findingLine}>
                  {finding.category.toUpperCase()}: {finding.message} ({finding.severity})
                </Text>
              ))}
            </View>
          ) : (
            <Text style={styles.resultPlaceholder}>Waiting for scan result…</Text>
          )}

          <TouchableOpacity style={styles.secondaryButton} onPress={flushQueue}>
            <Text style={styles.secondaryButtonText}>Retry queued uploads</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  };

  if (screen === "login") {
    return renderLogin();
  }

  if (screen === "dashboard") {
    return renderDashboard();
  }

  if (screen === "settings") {
    return renderSettings();
  }

  if (screen === "history") {
    return renderHistory();
  }

  return renderScan();
}

const mapFindingBox = (bbox: number[], imgWidth: number, imgHeight: number) => {
  const [x, y, w, h] = bbox;
  const previewWidth = Dimensions.get("window").width - 48;
  const previewHeight = previewWidth * 0.6;
  const scaleX = previewWidth / imgWidth;
  const scaleY = previewHeight / imgHeight;

  return {
    position: "absolute" as const,
    left: x * scaleX,
    top: y * scaleY,
    width: w * scaleX,
    height: h * scaleY,
    borderWidth: 2,
    borderColor: "#F25C54",
  };
};

const computeSharpness = async (snapshot: { preview: ImageManipulator.ImageResult }) => {
  if (!snapshot.preview.base64) {
    return 0;
  }
  const buffer = Buffer.from(snapshot.preview.base64, "base64");
  const decoded = jpeg.decode(buffer, { useTArray: true });
  const { data, width, height } = decoded;

  let sum = 0;
  let sumSq = 0;
  let count = 0;
  for (let y = 0; y < height - 1; y += 2) {
    for (let x = 0; x < width - 1; x += 2) {
      const idx = (y * width + x) * 4;
      const idxRight = (y * width + (x + 1)) * 4;
      const idxDown = ((y + 1) * width + x) * 4;
      const lum = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
      const lumRight = 0.299 * data[idxRight] + 0.587 * data[idxRight + 1] + 0.114 * data[idxRight + 2];
      const lumDown = 0.299 * data[idxDown] + 0.587 * data[idxDown + 1] + 0.114 * data[idxDown + 2];
      const edge = Math.abs(lum - lumRight) + Math.abs(lum - lumDown);
      sum += edge;
      sumSq += edge * edge;
      count += 1;
    }
  }

  const mean = sum / count;
  const variance = sumSq / count - mean * mean;
  return variance;
};

const average = (values: number[]) => values.reduce((acc, v) => acc + v, 0) / values.length;

const varianceOf = (values: number[], mean: number) =>
  values.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / values.length;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B1F2A",
  },
  loginContainer: {
    flex: 1,
    backgroundColor: "#DFF6E0",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  loginCard: {
    width: "100%",
    backgroundColor: "#E5E7EB",
    borderRadius: 18,
    padding: 24,
    gap: 12,
    alignItems: "center",
  },
  loginLogoWrap: {
    width: 72,
    height: 72,
    borderRadius: 18,
    backgroundColor: "#F8FAFC",
    alignItems: "center",
    justifyContent: "center",
  },
  loginLogo: {
    width: 48,
    height: 48,
  },
  loginTitle: {
    color: "#0B1F2A",
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
  },
  loginSubtitle: {
    color: "#4B5563",
    fontSize: 13,
    textAlign: "center",
  },
  input: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#0B1F2A",
    borderWidth: 1,
    borderColor: "#CBD5E1",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    paddingHorizontal: 12,
  },
  inputFlex: {
    flex: 1,
    paddingVertical: 10,
    color: "#0B1F2A",
  },
  eyeButton: {
    paddingVertical: 6,
    paddingHorizontal: 8,
  },
  eyeButtonText: {
    color: "#0B1F2A",
    fontWeight: "600",
    fontSize: 12,
  },
  errorText: {
    color: "#F87171",
    alignSelf: "flex-start",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 12,
    gap: 12,
  },
  headerText: {
    flex: 1,
  },
  backButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#38BDF8",
  },
  backButtonText: {
    color: "#38BDF8",
    fontSize: 12,
    fontWeight: "600",
  },
  logoBadge: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: "#F8FAFC",
    alignItems: "center",
    justifyContent: "center",
  },
  logo: {
    width: 40,
    height: 40,
  },
  title: {
    color: "#F8FAFC",
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    color: "#94A3B8",
    fontSize: 12,
    marginTop: 2,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0B1F2A",
  },
  permissionText: {
    color: "#fff",
    marginBottom: 16,
  },
  cameraFrame: {
    flex: 1.2,
    margin: 16,
    borderRadius: 18,
    overflow: "hidden",
  },
  camera: {
    flex: 1,
  },
  overlay: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.55)",
    padding: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  overlayText: {
    color: "#fff",
    fontWeight: "600",
  },
  panel: {
    flex: 1,
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  progressBar: {
    height: 6,
    backgroundColor: "#1F3A44",
    borderRadius: 8,
    overflow: "hidden",
    marginBottom: 12,
  },
  progressFill: {
    height: 6,
    backgroundColor: "#38BDF8",
  },
  resultTitle: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 6,
  },
  resultLine: {
    color: "#E2E8F0",
    marginBottom: 4,
  },
  disclaimer: {
    color: "#94A3B8",
    fontSize: 12,
    marginTop: 8,
  },
  previewContainer: {
    marginTop: 12,
    backgroundColor: "#0F172A",
    borderRadius: 12,
    padding: 12,
  },
  previewImage: {
    width: "100%",
    height: Dimensions.get("window").width * 0.6,
    borderRadius: 10,
  },
  findingLine: {
    color: "#CBD5F5",
    fontSize: 12,
    marginTop: 4,
  },
  resultPlaceholder: {
    color: "#94A3B8",
  },
  primaryButton: {
    backgroundColor: "#38BDF8",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
    width: "100%",
  },
  primaryButtonText: {
    color: "#0B1F2A",
    fontWeight: "600",
  },
  closeButton: {
    borderWidth: 1,
    borderColor: "#94A3B8",
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    alignItems: "center",
    width: "100%",
  },
  closeButtonText: {
    color: "#475569",
    fontWeight: "600",
  },
  secondaryButton: {
    marginTop: 12,
    paddingVertical: 10,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#38BDF8",
    borderRadius: 8,
  },
  secondaryButtonText: {
    color: "#38BDF8",
  },
  dashboardPanel: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    color: "#F8FAFC",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 12,
  },
  actionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  actionButton: {
    flexBasis: "48%",
    backgroundColor: "#111827",
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: "#1F2937",
  },
  actionText: {
    color: "#E2E8F0",
    fontWeight: "600",
  },
  logoutButton: {
    borderColor: "#F25C54",
  },
  logoutText: {
    color: "#F25C54",
    fontWeight: "600",
  },
  contentCard: {
    margin: 16,
    padding: 16,
    borderRadius: 14,
    backgroundColor: "#0F172A",
  },
  historyList: {
    padding: 16,
    gap: 12,
  },
  historyCard: {
    backgroundColor: "#0F172A",
    borderRadius: 14,
    padding: 14,
  },
  historyTitle: {
    color: "#F8FAFC",
    fontWeight: "600",
  },
  historyMeta: {
    color: "#94A3B8",
    fontSize: 12,
    marginTop: 4,
  },
});
