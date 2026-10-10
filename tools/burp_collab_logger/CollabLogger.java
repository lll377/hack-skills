import burp.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

public class CollabLogger implements IBurpExtender {
  private static final Path ROOT = Paths.get("C:/Users/Administrator/Desktop/hack-skills/evidence");
  private static final Path STATE = ROOT.resolve("collab_logger_state.json");
  private static final Path INTERACTIONS = ROOT.resolve("collab_logger_interactions.json");
  private volatile boolean running = true;

  public void registerExtenderCallbacks(IBurpExtenderCallbacks c) {
    c.setExtensionName("CollabLogger");
    try {
      Files.createDirectories(ROOT);
      IBurpCollaboratorClientContext ctx = c.createBurpCollaboratorClientContext();
      String payload = ctx.generatePayload(false);
      writeState(payload, ctx.getCollaboratorServerLocation(), null);
      Thread t = new Thread(() -> pollLoop(c, ctx, payload), "CollabLogger-Poll");
      t.setDaemon(true);
      t.start();
    } catch (Exception e) {
      try {
        writeState(null, null, e.toString());
      } catch (Exception ignored) {}
    }
  }

  private void pollLoop(IBurpExtenderCallbacks c, IBurpCollaboratorClientContext ctx, String payload) {
    while (running) {
      try {
        List<IBurpCollaboratorInteraction> xs = ctx.fetchAllCollaboratorInteractions();
        writeInteractions(payload, ctx.getCollaboratorServerLocation(), xs, null);
      } catch (Exception e) {
        try {
          writeInteractions(payload, ctx.getCollaboratorServerLocation(), Collections.emptyList(), e.toString());
        } catch (Exception ignored) {}
      }
      try { Thread.sleep(3000); } catch (InterruptedException ie) { running = false; }
    }
  }

  private static void writeState(String payload, String server, String error) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("{\n");
    sb.append("  \"updatedAt\": \"").append(esc(Instant.now().toString())).append("\",");
    sb.append("\n  \"payload\": ").append(jsonOrNull(payload)).append(",");
    sb.append("\n  \"server\": ").append(jsonOrNull(server)).append(",");
    sb.append("\n  \"error\": ").append(jsonOrNull(error)).append("\n");
    sb.append("}\n");
    Files.writeString(STATE, sb.toString(), StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
  }

  private static void writeInteractions(String payload, String server, List<IBurpCollaboratorInteraction> xs, String error) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("{\n");
    sb.append("  \"updatedAt\": \"").append(esc(Instant.now().toString())).append("\",");
    sb.append("\n  \"payload\": ").append(jsonOrNull(payload)).append(",");
    sb.append("\n  \"server\": ").append(jsonOrNull(server)).append(",");
    sb.append("\n  \"error\": ").append(jsonOrNull(error)).append(",");
    sb.append("\n  \"count\": ").append(xs.size()).append(",");
    sb.append("\n  \"interactions\": [");
    for (int i = 0; i < xs.size(); i++) {
      if (i > 0) sb.append(",");
      Map<?,?> props = xs.get(i).getProperties();
      sb.append("\n    {");
      boolean first = true;
      for (Map.Entry<?,?> e : props.entrySet()) {
        if (!first) sb.append(",");
        first = false;
        sb.append("\n      \"").append(esc(String.valueOf(e.getKey()))).append("\": ").append(jsonOrNull(String.valueOf(e.getValue())));
      }
      if (!props.isEmpty()) sb.append("\n    }"); else sb.append("}");
    }
    if (!xs.isEmpty()) sb.append("\n  ");
    sb.append("]\n}\n");
    Files.writeString(INTERACTIONS, sb.toString(), StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
  }

  private static String jsonOrNull(String s) {
    return s == null ? "null" : "\"" + esc(s) + "\"";
  }

  private static String esc(String s) {
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t");
  }
}
