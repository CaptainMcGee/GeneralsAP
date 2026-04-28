using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization.Metadata;

namespace GeneralsAP.Bridge;

internal static partial class Program
{
    private const string VersionText = "GeneralsAPBridge 0.2.0";
    private const string SlotDataFileName = "Seed-Slot-Data.json";
    private const string GameName = "Command & Conquer Generals: Zero Hour";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        TypeInfoResolver = new DefaultJsonTypeInfoResolver(),
    };

    public static int Main(string[] args)
    {
        try
        {
            BridgeArgs parsed = BridgeArgs.Parse(args);
            if (parsed.ShowHelp)
            {
                Console.WriteLine(BridgeArgs.HelpText);
                return 0;
            }
            if (parsed.ShowVersion)
            {
                Console.WriteLine(VersionText);
                return 0;
            }

            if (parsed.IsNetworkMode)
            {
                return RunNetworkBridgeAsync(parsed).GetAwaiter().GetResult();
            }

            if (parsed.Once)
            {
                BridgeCycleResult result = RunCycle(parsed);
                Console.WriteLine($"[GeneralsAPBridge] Ready: completedChecks={result.CompletedChecks} completedLocations={result.CompletedLocations} merged={result.Merged}");
                return 0;
            }

            Console.WriteLine($"[GeneralsAPBridge] Monitoring {parsed.ArchipelagoDir}");
            while (true)
            {
                BridgeCycleResult result = RunCycle(parsed);
                if (result.Merged)
                {
                    Console.WriteLine($"[GeneralsAPBridge] Merged outbound: completedChecks={result.CompletedChecks} completedLocations={result.CompletedLocations}");
                }
                Thread.Sleep(TimeSpan.FromSeconds(Math.Max(parsed.PollIntervalSeconds, 0.1)));
                parsed.ResetSession = false;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"ERROR: {ex.Message}");
            return 1;
        }
    }

    private static BridgeCycleResult RunCycle(BridgeArgs args)
    {
        Directory.CreateDirectory(args.ArchipelagoDir);

        string slotDataPath = MaterializeSlotData(args);
        JsonObject slotData = LoadObject(slotDataPath, "slot data");
        Dictionary<string, int> runtimeKeyToLocationId = BuildRuntimeKeyMap(slotData);

        string sessionPath = GetSessionPath(args);
        JsonObject session = LoadOrCreateSession(sessionPath, slotData, args.ResetSession);
        bool sessionChanged = args.ResetSession || !File.Exists(sessionPath);

        string outboundPath = Path.Combine(args.ArchipelagoDir, "Bridge-Outbound.json");
        if (File.Exists(outboundPath))
        {
            JsonObject outbound = LoadObject(outboundPath, "outbound bridge state");
            sessionChanged |= MergeOutbound(session, outbound, runtimeKeyToLocationId);
        }

        if (sessionChanged)
        {
            AtomicWriteJson(sessionPath, session);
        }

        JsonObject inbound = BuildInbound(session, slotData, slotDataPath);
        AtomicWriteJson(Path.Combine(args.ArchipelagoDir, "Bridge-Inbound.json"), inbound);
        AppendEvent(args.ArchipelagoDir, sessionChanged ? "cycle_merged" : "cycle_ready", inbound);

        return new BridgeCycleResult(
            CountArray(session, "completedChecks"),
            CountArray(session, "completedLocations"),
            sessionChanged
        );
    }

    private static string MaterializeSlotData(BridgeArgs args)
    {
        string targetPath = Path.Combine(args.ArchipelagoDir, SlotDataFileName);
        if (!string.IsNullOrWhiteSpace(args.SlotDataSource))
        {
            string sourcePath = Path.GetFullPath(args.SlotDataSource);
            if (!File.Exists(sourcePath))
            {
                throw new FileNotFoundException($"slot data source missing: {sourcePath}");
            }

            if (!Path.GetFullPath(targetPath).Equals(sourcePath, StringComparison.OrdinalIgnoreCase))
            {
                Directory.CreateDirectory(args.ArchipelagoDir);
                File.Copy(sourcePath, targetPath, overwrite: true);
            }
        }

        if (!File.Exists(targetPath))
        {
            throw new FileNotFoundException($"missing {SlotDataFileName}; pass --slot-data for file-bridge mode");
        }

        return targetPath;
    }

    private static string GetSessionPath(BridgeArgs args)
    {
        if (!string.IsNullOrWhiteSpace(args.SessionPath))
        {
            return args.SessionPath;
        }
        string fileName = args.IsNetworkMode ? "BridgeSession.json" : "LocalBridgeSession.json";
        return Path.Combine(args.ArchipelagoDir, fileName);
    }

    private static JsonObject LoadOrCreateSession(string sessionPath, JsonObject slotData, bool resetSession)
    {
        JsonObject session = resetSession || !File.Exists(sessionPath)
            ? new JsonObject()
            : LoadObject(sessionPath, "local bridge session");

        string seedId = GetString(slotData, "seedId", "unknown-seed");
        string slotName = GetString(slotData, "slotName", "Unknown Slot");
        string sessionNonce = GetString(slotData, "sessionNonce", "");

        SetDefault(session, "sessionVersion", 1);
        SetDefault(session, "seedId", seedId);
        SetDefault(session, "slotName", slotName);
        SetDefault(session, "sessionNonce", sessionNonce);
        SetDefault(session, "unlockedUnits", new JsonArray());
        SetDefault(session, "unlockedBuildings", new JsonArray());
        SetDefault(session, "unlockedGroupIds", new JsonArray());
        SetDefault(session, "unlockedGenerals", new JsonArray());
        SetDefault(session, "startingGenerals", new JsonArray());
        SetDefault(session, "completedLocations", new JsonArray());
        SetDefault(session, "completedChecks", new JsonArray());
        SetDefault(session, "capturedBuildingState", new JsonArray());
        SetDefault(session, "supplyPileState", new JsonArray());
        SetDefault(session, "receivedItems", new JsonArray());
        SetDefault(session, "lastAppliedReceivedItemSequence", -1);
        SetDefault(session, "sessionOptions", new JsonObject
        {
            ["startingCashBonus"] = 0,
            ["productionMultiplier"] = 1.0,
            ["disableZoomLimit"] = false,
            ["starterGenerals"] = new JsonArray(),
        });
        SetDefault(session, "notes", new JsonArray());

        return session;
    }

    private static bool MergeOutbound(JsonObject session, JsonObject outbound, Dictionary<string, int> runtimeKeyToLocationId)
    {
        SortedSet<string> completedChecks = ToStringSet(session["completedChecks"]);
        SortedSet<int> completedLocations = ToIntSet(session["completedLocations"]);
        HashSet<int> selectedLocationIds = new(runtimeKeyToLocationId.Values);
        int beforeChecks = completedChecks.Count;
        int beforeLocations = completedLocations.Count;

        foreach (string runtimeKey in ToStringSet(outbound["completedChecks"]))
        {
            if (!runtimeKeyToLocationId.TryGetValue(runtimeKey, out int locationId))
            {
                throw new InvalidOperationException($"unknown runtime check key: {runtimeKey}");
            }
            completedChecks.Add(runtimeKey);
            completedLocations.Add(locationId);
        }

        foreach (int locationId in ToIntSet(outbound["completedLocations"]))
        {
            if (!selectedLocationIds.Contains(locationId))
            {
                throw new InvalidOperationException($"unknown AP location id: {locationId}");
            }
            completedLocations.Add(locationId);
        }

        session["completedChecks"] = ToJsonArray(completedChecks);
        session["completedLocations"] = ToJsonArray(completedLocations);
        return completedChecks.Count != beforeChecks || completedLocations.Count != beforeLocations;
    }

    private static JsonObject BuildInbound(JsonObject session, JsonObject slotData, string slotDataPath)
    {
        return new JsonObject
        {
            ["bridgeVersion"] = 1,
            ["sessionVersion"] = GetInt(session, "sessionVersion", 1),
            ["seedId"] = GetString(session, "seedId", GetString(slotData, "seedId", "unknown-seed")),
            ["slotName"] = GetString(session, "slotName", GetString(slotData, "slotName", "Unknown Slot")),
            ["sessionNonce"] = GetString(session, "sessionNonce", GetString(slotData, "sessionNonce", "")),
            ["unlockedUnits"] = CloneArray(session["unlockedUnits"]),
            ["unlockedBuildings"] = CloneArray(session["unlockedBuildings"]),
            ["unlockedGroupIds"] = CloneArray(session["unlockedGroupIds"]),
            ["unlockedGenerals"] = CloneArray(session["unlockedGenerals"]),
            ["startingGenerals"] = CloneArray(session["startingGenerals"]),
            ["completedLocations"] = CloneArray(session["completedLocations"]),
            ["completedChecks"] = CloneArray(session["completedChecks"]),
            ["capturedBuildingState"] = CloneArray(session["capturedBuildingState"]),
            ["supplyPileState"] = CloneArray(session["supplyPileState"]),
            ["receivedItems"] = CloneArray(session["receivedItems"]),
            ["sessionOptions"] = session["sessionOptions"]?.DeepClone(),
            ["slotDataVersion"] = GetInt(slotData, "version", 0),
            ["slotDataPath"] = SlotDataFileName,
            ["slotDataHash"] = FileSha256(slotDataPath),
        };
    }

    private static Dictionary<string, int> BuildRuntimeKeyMap(JsonObject slotData)
    {
        Dictionary<string, int> mapping = new(StringComparer.Ordinal);
        JsonObject maps = RequiredObject(slotData, "maps", "slot data");
        foreach (KeyValuePair<string, JsonNode?> entry in maps)
        {
            JsonObject map = AsObject(entry.Value, $"map {entry.Key}");
            AddLocation(mapping, RequiredObject(map, "missionVictory", entry.Key), $"{entry.Key}.missionVictory");

            foreach (JsonNode? clusterNode in AsArray(map["clusters"]))
            {
                JsonObject cluster = AsObject(clusterNode, $"{entry.Key}.cluster");
                foreach (JsonNode? unitNode in AsArray(cluster["units"]))
                {
                    AddLocation(mapping, AsObject(unitNode, $"{entry.Key}.cluster.unit"), $"{entry.Key}.cluster.unit");
                }
            }

            foreach (JsonNode? capturedNode in AsArray(map["capturedBuildings"]))
            {
                AddLocation(mapping, AsObject(capturedNode, $"{entry.Key}.capturedBuilding"), $"{entry.Key}.capturedBuilding");
            }

            foreach (JsonNode? supplyNode in AsArray(map["supplyPileThresholds"]))
            {
                AddLocation(mapping, AsObject(supplyNode, $"{entry.Key}.supplyPileThreshold"), $"{entry.Key}.supplyPileThreshold");
            }
        }

        return mapping;
    }

    private static Dictionary<int, string> BuildLocationIdToRuntimeKeyMap(Dictionary<string, int> runtimeKeyToLocationId)
    {
        Dictionary<int, string> mapping = new();
        foreach ((string runtimeKey, int locationId) in runtimeKeyToLocationId)
        {
            mapping[locationId] = runtimeKey;
        }
        return mapping;
    }

    private static void AddLocation(Dictionary<string, int> mapping, JsonObject location, string context)
    {
        string runtimeKey = GetString(location, "runtimeKey", "");
        int apLocationId = GetInt(location, "apLocationId", 0);
        if (string.IsNullOrWhiteSpace(runtimeKey) || apLocationId <= 0)
        {
            throw new InvalidOperationException($"{context} missing runtimeKey/apLocationId");
        }
        if (mapping.TryGetValue(runtimeKey, out int existing) && existing != apLocationId)
        {
            throw new InvalidOperationException($"{context} duplicate runtimeKey maps to two IDs: {runtimeKey}");
        }
        mapping[runtimeKey] = apLocationId;
    }

    private static JsonObject LoadObject(string path, string label)
    {
        JsonNode? node = JsonNode.Parse(File.ReadAllText(path));
        if (node is not JsonObject obj)
        {
            throw new InvalidOperationException($"{label} is not a JSON object: {path}");
        }
        return obj;
    }

    private static JsonObject RequiredObject(JsonObject obj, string key, string context)
    {
        return AsObject(obj[key], $"{context}.{key}");
    }

    private static JsonObject AsObject(JsonNode? node, string context)
    {
        if (node is JsonObject obj)
        {
            return obj;
        }
        throw new InvalidOperationException($"{context} is not a JSON object");
    }

    private static JsonArray AsArray(JsonNode? node)
    {
        return node as JsonArray ?? new JsonArray();
    }

    private static JsonArray CloneArray(JsonNode? node)
    {
        return node is JsonArray array ? (JsonArray)array.DeepClone() : new JsonArray();
    }

    private static string GetString(JsonObject obj, string key, string fallback)
    {
        return obj[key]?.GetValue<string>() ?? fallback;
    }

    private static int GetInt(JsonObject obj, string key, int fallback)
    {
        JsonNode? node = obj[key];
        if (node is null)
        {
            return fallback;
        }
        if (node is JsonValue value && value.GetValueKind() == JsonValueKind.Number && value.TryGetValue(out int number))
        {
            return number;
        }
        if (int.TryParse(node.ToString(), out int parsed))
        {
            return parsed;
        }
        return fallback;
    }

    private static void SetDefault(JsonObject obj, string key, JsonNode value)
    {
        if (obj[key] is null)
        {
            obj[key] = value;
        }
    }

    private static void SetDefault(JsonObject obj, string key, string value)
    {
        if (obj[key] is null)
        {
            obj[key] = value;
        }
    }

    private static void SetDefault(JsonObject obj, string key, int value)
    {
        if (obj[key] is null)
        {
            obj[key] = value;
        }
    }

    private static SortedSet<string> ToStringSet(JsonNode? node)
    {
        SortedSet<string> values = new(StringComparer.Ordinal);
        if (node is not JsonArray array)
        {
            return values;
        }
        foreach (JsonNode? item in array)
        {
            string value = item?.ToString().Trim() ?? "";
            if (value.Length > 0)
            {
                values.Add(value);
            }
        }
        return values;
    }

    private static SortedSet<int> ToIntSet(JsonNode? node)
    {
        SortedSet<int> values = new();
        if (node is not JsonArray array)
        {
            return values;
        }
        foreach (JsonNode? item in array)
        {
            if (item is null)
            {
                continue;
            }
            if (item is JsonValue value && value.GetValueKind() == JsonValueKind.Number && value.TryGetValue(out int number))
            {
                values.Add(number);
            }
            else if (int.TryParse(item.ToString(), out int parsed))
            {
                values.Add(parsed);
            }
        }
        return values;
    }

    private static JsonArray ToJsonArray(IEnumerable<string> values)
    {
        JsonArray array = new();
        foreach (string value in values)
        {
            array.Add(value);
        }
        return array;
    }

    private static JsonArray ToJsonArray(IEnumerable<int> values)
    {
        JsonArray array = new();
        foreach (int value in values)
        {
            array.Add(value);
        }
        return array;
    }

    private static int CountArray(JsonObject obj, string key)
    {
        return obj[key] is JsonArray array ? array.Count : 0;
    }

    private static void AtomicWriteJson(string path, JsonObject payload)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string tempPath = path + ".tmp";
        File.WriteAllText(tempPath, payload.ToJsonString(JsonOptions) + Environment.NewLine);
        File.Move(tempPath, path, overwrite: true);
    }

    private static void AppendEvent(string archipelagoDir, string eventName, JsonObject inbound)
    {
        string path = Path.Combine(archipelagoDir, "Bridge-Events.jsonl");
        JsonObject payload = new()
        {
            ["timestampUtc"] = DateTimeOffset.UtcNow.ToString("O"),
            ["event"] = eventName,
            ["seedId"] = inbound["seedId"]?.GetValue<string>(),
            ["slotName"] = inbound["slotName"]?.GetValue<string>(),
        };
        File.AppendAllText(path, payload.ToJsonString() + Environment.NewLine);
    }

    private static string FileSha256(string path)
    {
        byte[] digest = SHA256.HashData(File.ReadAllBytes(path));
        return "sha256:" + Convert.ToHexString(digest).ToLowerInvariant();
    }
}

internal sealed class BridgeCycleResult(int completedChecks, int completedLocations, bool merged, int submittedLocations = 0)
{
    public int CompletedChecks { get; } = completedChecks;
    public int CompletedLocations { get; } = completedLocations;
    public bool Merged { get; } = merged;
    public int SubmittedLocations { get; } = submittedLocations;
}

internal sealed class BridgeArgs
{
    public string ArchipelagoDir { get; private set; } = Path.GetFullPath(Path.Combine(Environment.CurrentDirectory, "UserData", "Archipelago"));
    public string? SessionPath { get; private set; }
    public string? SlotDataSource { get; private set; }
    public string? ConnectAddress { get; private set; }
    public string? SlotName { get; private set; }
    public string? Password { get; private set; }
    public string? ClientUuid { get; private set; }
    public bool IsNetworkMode => !string.IsNullOrWhiteSpace(ConnectAddress);
    public bool ResetSession { get; set; }
    public bool Once { get; private set; }
    public bool ShowHelp { get; private set; }
    public bool ShowVersion { get; private set; }
    public double PollIntervalSeconds { get; private set; } = 0.5;

    public const string HelpText =
        "GeneralsAPBridge\n" +
        "  --archipelago-dir <path>  UserData/Archipelago directory\n" +
        "  --slot-data <path>        Seed-Slot-Data.json received from AP/generator\n" +
        "  --connect <host:port>     Connect to Archipelago server and use live slot_data\n" +
        "  --slot-name <name>        Archipelago slot name for --connect\n" +
        "  --password <password>     Optional Archipelago room password\n" +
        "  --uuid <uuid>             Optional stable client UUID\n" +
        "  --session <path>          Optional LocalBridgeSession.json path\n" +
        "  --reset-session           Reset local bridge session before cycle\n" +
        "  --once                    Run one bridge cycle and exit\n" +
        "  --poll-interval <sec>     Loop sleep interval\n" +
        "  --version                 Print version\n";

    public static BridgeArgs Parse(string[] args)
    {
        BridgeArgs parsed = new();
        for (int i = 0; i < args.Length; i++)
        {
            string arg = args[i];
            switch (arg)
            {
                case "--help":
                case "-h":
                    parsed.ShowHelp = true;
                    break;
                case "--version":
                    parsed.ShowVersion = true;
                    break;
                case "--once":
                    parsed.Once = true;
                    break;
                case "--reset-session":
                    parsed.ResetSession = true;
                    break;
                case "--archipelago-dir":
                    parsed.ArchipelagoDir = Path.GetFullPath(RequireValue(args, ref i, arg));
                    break;
                case "--session":
                    parsed.SessionPath = Path.GetFullPath(RequireValue(args, ref i, arg));
                    break;
                case "--slot-data":
                    parsed.SlotDataSource = Path.GetFullPath(RequireValue(args, ref i, arg));
                    break;
                case "--connect":
                case "--server":
                    parsed.ConnectAddress = RequireValue(args, ref i, arg);
                    break;
                case "--slot-name":
                case "--slot":
                    parsed.SlotName = RequireValue(args, ref i, arg);
                    break;
                case "--password":
                    parsed.Password = RequireValue(args, ref i, arg);
                    break;
                case "--uuid":
                    parsed.ClientUuid = RequireValue(args, ref i, arg);
                    break;
                case "--poll-interval":
                    if (!double.TryParse(RequireValue(args, ref i, arg), out double seconds))
                    {
                        throw new ArgumentException("--poll-interval must be numeric seconds");
                    }
                    parsed.PollIntervalSeconds = seconds;
                    break;
                default:
                    throw new ArgumentException($"unknown argument: {arg}");
            }
        }
        return parsed;
    }

    private static string RequireValue(string[] args, ref int index, string option)
    {
        if (index + 1 >= args.Length)
        {
            throw new ArgumentException($"{option} requires a value");
        }
        index++;
        return args[index];
    }
}
