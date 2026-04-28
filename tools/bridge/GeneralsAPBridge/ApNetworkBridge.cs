using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace GeneralsAP.Bridge;

internal static partial class Program
{
    private const int ClientGoalStatus = 30;
    private const int FullRemoteItemsHandling = 0b111;
    private const int StartingMoneyPerItem = 2000;
    private const double ProductionMultiplierPerItem = 0.25;
    private const double ProductionMultiplierCap = 4.0;

    private static readonly Dictionary<string, string> RuntimeGroupByItemName = new(StringComparer.Ordinal)
    {
        ["Shared Rocket Infantry"] = "Shared_RocketInfantry",
        ["Shared Tanks"] = "Shared_Tanks",
        ["Shared Machine Gun Vehicles"] = "Shared_MachineGunVehicles",
        ["Shared Artillery"] = "Shared_Artillery",
        ["Upgrade Radar"] = "Upgrade_Radar",
    };

    private static async Task<int> RunNetworkBridgeAsync(BridgeArgs args)
    {
        if (string.IsNullOrWhiteSpace(args.SlotName))
        {
            throw new ArgumentException("--slot-name is required with --connect");
        }

        Directory.CreateDirectory(args.ArchipelagoDir);
        Uri serverUri = NormalizeServerUri(args.ConnectAddress!);
        NetworkBridgeState state = new(args);

        using ClientWebSocket socket = new();
        await socket.ConnectAsync(serverUri, CancellationToken.None);
        Console.WriteLine($"[GeneralsAPBridge] Connected socket: {serverUri}");

        DateTime handshakeDeadlineUtc = DateTime.UtcNow.AddSeconds(30);
        Task<string?> receiveTask = ReceiveTextMessageAsync(socket);
        while (socket.State == WebSocketState.Open)
        {
            bool ready = state.Authenticated && state.SlotData is not null;
            TimeSpan pollDelay = ready
                ? TimeSpan.FromSeconds(Math.Max(args.PollIntervalSeconds, 0.1))
                : TimeSpan.FromSeconds(5);

            Task completed = await Task.WhenAny(receiveTask, Task.Delay(pollDelay));
            if (completed != receiveTask)
            {
                if (!ready)
                {
                    if (DateTime.UtcNow > handshakeDeadlineUtc)
                    {
                        throw new TimeoutException("Timed out before Archipelago authentication completed.");
                    }
                    continue;
                }

                if (args.Once)
                {
                    DateTime receivedItemsDeadlineUtc = state.AuthenticatedAtUtc?.AddSeconds(1) ?? handshakeDeadlineUtc;
                    if (state.ReceivedItemsSynced || DateTime.UtcNow > receivedItemsDeadlineUtc)
                    {
                        BridgeCycleResult onceResult = await RunNetworkCycleAsync(socket, args, state);
                        Console.WriteLine($"[GeneralsAPBridge] Ready: completedChecks={onceResult.CompletedChecks} completedLocations={onceResult.CompletedLocations} submitted={onceResult.SubmittedLocations}");
                        return 0;
                    }
                    continue;
                }

                BridgeCycleResult pollResult = await RunNetworkCycleAsync(socket, args, state);
                Console.WriteLine($"[GeneralsAPBridge] Ready: completedChecks={pollResult.CompletedChecks} completedLocations={pollResult.CompletedLocations} submitted={pollResult.SubmittedLocations}");
                continue;
            }

            string? message = await receiveTask;
            receiveTask = ReceiveTextMessageAsync(socket);
            if (message is null)
            {
                break;
            }

            foreach (JsonObject packet in ParsePacketArray(message))
            {
                await ProcessNetworkPacketAsync(socket, args, state, packet);
            }

            if (state.Authenticated && state.SlotData is not null)
            {
                BridgeCycleResult packetResult = await RunNetworkCycleAsync(socket, args, state);
                if (args.Once && state.ReceivedItemsSynced)
                {
                    Console.WriteLine($"[GeneralsAPBridge] Ready: completedChecks={packetResult.CompletedChecks} completedLocations={packetResult.CompletedLocations} submitted={packetResult.SubmittedLocations}");
                    return 0;
                }
                if (packetResult.Merged || packetResult.SubmittedLocations > 0)
                {
                    Console.WriteLine($"[GeneralsAPBridge] Cycle: completedChecks={packetResult.CompletedChecks} completedLocations={packetResult.CompletedLocations} submitted={packetResult.SubmittedLocations}");
                }
            }
        }

        throw new InvalidOperationException("Archipelago socket closed.");
    }

    private static async Task ProcessNetworkPacketAsync(ClientWebSocket socket, BridgeArgs args, NetworkBridgeState state, JsonObject packet)
    {
        string cmd = GetString(packet, "cmd", "");
        switch (cmd)
        {
            case "RoomInfo":
                if (!state.DataPackageRequested)
                {
                    await SendPacketsAsync(socket, new JsonObject
                    {
                        ["cmd"] = "GetDataPackage",
                        ["games"] = new JsonArray(GameName),
                    });
                    state.DataPackageRequested = true;
                }
                break;

            case "DataPackage":
                state.LoadDataPackage(packet);
                if (!state.ConnectSent)
                {
                    await SendConnectAsync(socket, args);
                    state.ConnectSent = true;
                }
                break;

            case "Connected":
                state.Authenticated = true;
                state.AuthenticatedAtUtc = DateTime.UtcNow;
                state.Team = GetInt(packet, "team", 0);
                state.Slot = GetInt(packet, "slot", 0);
                state.SetServerLocationState(packet);
                state.SlotData = RequiredObject(packet, "slot_data", "Connected");
                Console.WriteLine($"[GeneralsAPBridge] Authenticated slot={state.Slot} team={state.Team}");
                break;

            case "ReceivedItems":
                state.ReceivedItemsSynced = true;
                state.ApplyReceivedItemsPacket(packet);
                break;

            case "RoomUpdate":
                state.ApplyRoomUpdate(packet);
                break;

            case "ConnectionRefused":
                throw new InvalidOperationException("Connection refused: " + string.Join(", ", ToStringSet(packet["errors"])));

            case "InvalidPacket":
                throw new InvalidOperationException("Invalid packet from server: " + GetString(packet, "text", "(no text)"));

            case "Print":
            case "PrintJSON":
            case "Retrieved":
            case "SetReply":
                break;

            default:
                if (!string.IsNullOrWhiteSpace(cmd))
                {
                    Console.WriteLine($"[GeneralsAPBridge] Ignored server packet: {cmd}");
                }
                break;
        }
    }

    private static async Task SendConnectAsync(ClientWebSocket socket, BridgeArgs args)
    {
        string uuid = GetOrCreateClientUuid(args);
        await SendPacketsAsync(socket, new JsonObject
        {
            ["cmd"] = "Connect",
            ["password"] = args.Password,
            ["game"] = GameName,
            ["name"] = args.SlotName,
            ["uuid"] = uuid,
            ["version"] = new JsonObject
            {
                ["major"] = 0,
                ["minor"] = 6,
                ["build"] = 7,
                ["class"] = "Version",
            },
            ["items_handling"] = FullRemoteItemsHandling,
            ["tags"] = new JsonArray("GeneralsAPBridge"),
            ["slot_data"] = true,
        });
    }

    private static async Task<BridgeCycleResult> RunNetworkCycleAsync(ClientWebSocket socket, BridgeArgs args, NetworkBridgeState state)
    {
        JsonObject slotData = state.SlotData ?? throw new InvalidOperationException("network slot data missing");
        string slotDataPath = Path.Combine(args.ArchipelagoDir, SlotDataFileName);
        AtomicWriteJson(slotDataPath, slotData);

        Dictionary<string, int> runtimeKeyToLocationId = BuildRuntimeKeyMap(slotData);
        Dictionary<int, string> locationIdToRuntimeKey = BuildLocationIdToRuntimeKeyMap(runtimeKeyToLocationId);
        HashSet<int> selectedLocationIds = new(runtimeKeyToLocationId.Values);

        string sessionPath = GetSessionPath(args);
        JsonObject session = LoadOrCreateSession(sessionPath, slotData, args.ResetSession);
        bool changed = args.ResetSession || !File.Exists(sessionPath);
        args.ResetSession = false;

        changed |= state.ApplyToSession(session, selectedLocationIds, locationIdToRuntimeKey);

        string outboundPath = Path.Combine(args.ArchipelagoDir, "Bridge-Outbound.json");
        if (File.Exists(outboundPath))
        {
            JsonObject outbound = LoadObject(outboundPath, "outbound bridge state");
            changed |= MergeOutbound(session, outbound, runtimeKeyToLocationId);
        }

        if (changed)
        {
            AtomicWriteJson(sessionPath, session);
        }

        JsonObject inbound = BuildInbound(session, slotData, slotDataPath);
        AtomicWriteJson(Path.Combine(args.ArchipelagoDir, "Bridge-Inbound.json"), inbound);
        AppendEvent(args.ArchipelagoDir, changed ? "network_cycle_merged" : "network_cycle_ready", inbound);

        List<int> toSubmit = ToIntSet(session["completedLocations"])
            .Where(selectedLocationIds.Contains)
            .Where(locationId => state.ServerKnownLocationIds.Contains(locationId))
            .Where(locationId => !state.ServerCheckedLocationIds.Contains(locationId))
            .Where(locationId => !state.SubmittedLocationIds.Contains(locationId))
            .OrderBy(locationId => locationId)
            .ToList();

        if (toSubmit.Count > 0)
        {
            await SendPacketsAsync(socket, new JsonObject
            {
                ["cmd"] = "LocationChecks",
                ["locations"] = ToJsonArray(toSubmit),
            });
            foreach (int locationId in toSubmit)
            {
                state.SubmittedLocationIds.Add(locationId);
                state.ServerCheckedLocationIds.Add(locationId);
            }
        }

        if (!state.GoalSent
            && runtimeKeyToLocationId.TryGetValue("mission.boss.victory", out int bossVictoryLocationId)
            && ToIntSet(session["completedLocations"]).Contains(bossVictoryLocationId))
        {
            await SendPacketsAsync(socket, new JsonObject
            {
                ["cmd"] = "StatusUpdate",
                ["status"] = ClientGoalStatus,
            });
            state.GoalSent = true;
        }

        return new BridgeCycleResult(
            CountArray(session, "completedChecks"),
            CountArray(session, "completedLocations"),
            changed,
            toSubmit.Count
        );
    }

    private static Uri NormalizeServerUri(string address)
    {
        string value = address.Trim();
        if (value.StartsWith("archipelago://", StringComparison.OrdinalIgnoreCase))
        {
            value = "ws://" + value["archipelago://".Length..];
        }
        else if (!value.Contains("://", StringComparison.Ordinal))
        {
            value = "ws://" + value;
        }
        Uri uri = new(value, UriKind.Absolute);
        if (uri.Scheme is not ("ws" or "wss"))
        {
            throw new ArgumentException("--connect must use ws://, wss://, archipelago://, or host:port");
        }
        return uri;
    }

    private static async Task SendPacketsAsync(ClientWebSocket socket, params JsonObject[] packets)
    {
        JsonArray array = new();
        foreach (JsonObject packet in packets)
        {
            array.Add(packet.DeepClone());
        }
        byte[] bytes = Encoding.UTF8.GetBytes(array.ToJsonString());
        await socket.SendAsync(bytes, WebSocketMessageType.Text, true, CancellationToken.None);
    }

    private static async Task<string?> ReceiveTextMessageAsync(ClientWebSocket socket)
    {
        MemoryStream stream = new();
        byte[] buffer = new byte[8192];

        while (true)
        {
            WebSocketReceiveResult result = await socket.ReceiveAsync(buffer, CancellationToken.None);

            if (result.MessageType == WebSocketMessageType.Close)
            {
                return null;
            }
            if (result.MessageType != WebSocketMessageType.Text)
            {
                continue;
            }

            stream.Write(buffer, 0, result.Count);
            if (result.EndOfMessage)
            {
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }
    }

    private static IEnumerable<JsonObject> ParsePacketArray(string message)
    {
        JsonNode? root = JsonNode.Parse(message);
        if (root is not JsonArray packets)
        {
            throw new InvalidOperationException("server message was not a packet array");
        }
        foreach (JsonNode? packet in packets)
        {
            yield return AsObject(packet, "server packet");
        }
    }

    private static string GetOrCreateClientUuid(BridgeArgs args)
    {
        if (!string.IsNullOrWhiteSpace(args.ClientUuid))
        {
            return args.ClientUuid;
        }

        string path = Path.Combine(args.ArchipelagoDir, "BridgeClientId.txt");
        if (File.Exists(path))
        {
            string existing = File.ReadAllText(path).Trim();
            if (!string.IsNullOrWhiteSpace(existing))
            {
                return existing;
            }
        }

        string created = Guid.NewGuid().ToString("N");
        Directory.CreateDirectory(args.ArchipelagoDir);
        File.WriteAllText(path, created + Environment.NewLine);
        return created;
    }

    private sealed class NetworkBridgeState
    {
        private readonly List<NetworkItemRecord> _receivedItems = [];

        public NetworkBridgeState(BridgeArgs args)
        {
            SlotName = args.SlotName ?? "";
        }

        public string SlotName { get; }
        public bool DataPackageRequested { get; set; }
        public bool ConnectSent { get; set; }
        public bool Authenticated { get; set; }
        public DateTime? AuthenticatedAtUtc { get; set; }
        public bool GoalSent { get; set; }
        public bool ReceivedItemsSynced { get; set; }
        public int Team { get; set; }
        public int Slot { get; set; }
        public JsonObject? SlotData { get; set; }
        public Dictionary<long, string> ItemNameById { get; } = new();
        public HashSet<int> ServerKnownLocationIds { get; } = new();
        public HashSet<int> ServerCheckedLocationIds { get; } = new();
        public HashSet<int> SubmittedLocationIds { get; } = new();

        public void LoadDataPackage(JsonObject packet)
        {
            JsonObject data = RequiredObject(packet, "data", "DataPackage");
            JsonObject games = RequiredObject(data, "games", "DataPackage.data");
            if (games[GameName] is not JsonObject game)
            {
                return;
            }
            JsonObject itemNameToId = RequiredObject(game, "item_name_to_id", GameName);
            ItemNameById.Clear();
            foreach ((string itemName, JsonNode? value) in itemNameToId)
            {
                if (TryGetLong(value, out long itemId))
                {
                    ItemNameById[itemId] = itemName;
                }
            }
        }

        public void SetServerLocationState(JsonObject packet)
        {
            ServerCheckedLocationIds.Clear();
            ServerKnownLocationIds.Clear();
            foreach (int locationId in ToIntSet(packet["checked_locations"]))
            {
                ServerCheckedLocationIds.Add(locationId);
                ServerKnownLocationIds.Add(locationId);
            }
            foreach (int locationId in ToIntSet(packet["missing_locations"]))
            {
                ServerKnownLocationIds.Add(locationId);
            }
        }

        public void ApplyRoomUpdate(JsonObject packet)
        {
            foreach (int locationId in ToIntSet(packet["checked_locations"]))
            {
                ServerCheckedLocationIds.Add(locationId);
            }
        }

        public void ApplyReceivedItemsPacket(JsonObject packet)
        {
            int startIndex = GetInt(packet, "index", 0);
            if (startIndex == 0)
            {
                _receivedItems.Clear();
            }

            JsonArray items = AsArray(packet["items"]);
            for (int offset = 0; offset < items.Count; offset++)
            {
                if (items[offset] is not JsonArray networkItem || networkItem.Count < 4)
                {
                    continue;
                }
                if (!TryGetLong(networkItem[0], out long itemId))
                {
                    continue;
                }
                _receivedItems.RemoveAll(item => item.Sequence == startIndex + offset);
                _receivedItems.Add(new NetworkItemRecord(
                    startIndex + offset,
                    itemId,
                    TryGetLong(networkItem[1], out long locationId) ? locationId : 0,
                    TryGetLong(networkItem[2], out long player) ? player : 0,
                    TryGetLong(networkItem[3], out long flags) ? flags : 0
                ));
            }
            _receivedItems.Sort((left, right) => left.Sequence.CompareTo(right.Sequence));
        }

        public bool ApplyToSession(JsonObject session, HashSet<int> selectedLocationIds, Dictionary<int, string> locationIdToRuntimeKey)
        {
            bool changed = false;

            changed |= SetString(session, "seedId", GetString(SlotData!, "seedId", "unknown-seed"));
            changed |= SetString(session, "slotName", GetString(SlotData!, "slotName", SlotName));
            changed |= SetString(session, "sessionNonce", GetString(SlotData!, "sessionNonce", ""));

            SortedSet<int> completedLocations = ToIntSet(session["completedLocations"]);
            SortedSet<string> completedChecks = ToStringSet(session["completedChecks"]);
            int beforeLocationCount = completedLocations.Count;
            int beforeCheckCount = completedChecks.Count;
            foreach (int locationId in ServerCheckedLocationIds)
            {
                if (!selectedLocationIds.Contains(locationId))
                {
                    continue;
                }
                completedLocations.Add(locationId);
                if (locationIdToRuntimeKey.TryGetValue(locationId, out string? runtimeKey))
                {
                    completedChecks.Add(runtimeKey);
                }
            }
            if (completedLocations.Count != beforeLocationCount)
            {
                session["completedLocations"] = ToJsonArray(completedLocations);
                changed = true;
            }
            if (completedChecks.Count != beforeCheckCount)
            {
                session["completedChecks"] = ToJsonArray(completedChecks);
                changed = true;
            }

            JsonArray runtimeItems = BuildRuntimeReceivedItems();
            if ((session["receivedItems"]?.ToJsonString() ?? "") != runtimeItems.ToJsonString())
            {
                session["receivedItems"] = runtimeItems;
                changed = true;
            }

            JsonObject options = BuildSessionOptionsFromItems();
            if ((session["sessionOptions"]?.ToJsonString() ?? "") != options.ToJsonString())
            {
                session["sessionOptions"] = options;
                changed = true;
            }

            return changed;
        }

        private JsonArray BuildRuntimeReceivedItems()
        {
            JsonArray result = new();
            foreach (NetworkItemRecord item in _receivedItems)
            {
                if (!ItemNameById.TryGetValue(item.ItemId, out string? itemName))
                {
                    continue;
                }
                if (!RuntimeGroupByItemName.TryGetValue(itemName, out string? groupId))
                {
                    continue;
                }
                result.Add(new JsonObject
                {
                    ["sequence"] = item.Sequence,
                    ["kind"] = "unlock_group",
                    ["groupId"] = groupId,
                    ["itemName"] = itemName,
                    ["apItemId"] = item.ItemId,
                    ["sourceLocationId"] = item.SourceLocationId,
                    ["sourcePlayer"] = item.SourcePlayer,
                    ["flags"] = item.Flags,
                });
            }
            return result;
        }

        private JsonObject BuildSessionOptionsFromItems()
        {
            Dictionary<string, int> counts = CountReceivedItemNames();
            int startingMoneyItems = counts.GetValueOrDefault("Progressive Starting Money");
            int productionItems = counts.GetValueOrDefault("Progressive Production");
            return new JsonObject
            {
                ["startingCashBonus"] = startingMoneyItems * StartingMoneyPerItem,
                ["productionMultiplier"] = Math.Min(ProductionMultiplierCap, 1.0 + productionItems * ProductionMultiplierPerItem),
                ["disableZoomLimit"] = false,
                ["starterGenerals"] = new JsonArray(),
            };
        }

        private Dictionary<string, int> CountReceivedItemNames()
        {
            Dictionary<string, int> counts = new(StringComparer.Ordinal);
            foreach (NetworkItemRecord item in _receivedItems)
            {
                if (!ItemNameById.TryGetValue(item.ItemId, out string? itemName))
                {
                    continue;
                }
                counts[itemName] = counts.GetValueOrDefault(itemName) + 1;
            }
            return counts;
        }

        private static bool SetString(JsonObject obj, string key, string value)
        {
            if (GetString(obj, key, "") == value)
            {
                return false;
            }
            obj[key] = value;
            return true;
        }
    }

    private sealed record NetworkItemRecord(int Sequence, long ItemId, long SourceLocationId, long SourcePlayer, long Flags);

    private static bool TryGetLong(JsonNode? node, out long value)
    {
        value = 0;
        if (node is null)
        {
            return false;
        }
        if (node is JsonValue jsonValue && jsonValue.GetValueKind() == JsonValueKind.Number && jsonValue.TryGetValue(out long number))
        {
            value = number;
            return true;
        }
        return long.TryParse(node.ToString(), out value);
    }
}
