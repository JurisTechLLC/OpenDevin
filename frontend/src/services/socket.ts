// Modified socket service for Vercel deployment using HTTP-based API calls
import { handleAssistantMessage } from "./actions";
import { getToken } from "./auth";
import toast from "../utils/toast";

// Check if we're in a Vercel environment (no WebSocket support)
const isVercelEnvironment = () =>
  typeof window !== "undefined" &&
  (window.location.hostname.includes("vercel.app") ||
    window.location.hostname.includes("vercel") ||
    !window.location.hostname.includes("localhost"));

class Socket {
  private static _socket: WebSocket | null = null;

  private static _httpMode: boolean = false;

  private static _token: string = "";

  // callbacks contain a list of callable functions
  // event: function, like:
  // open: [function1, function2]
  // message: [function1, function2]
  private static callbacks: {
    [K in keyof WebSocketEventMap]: ((data: WebSocketEventMap[K]) => void)[];
  } = {
    open: [],
    message: [],
    error: [],
    close: [],
  };

  private static initializing = false;

  public static tryInitialize(): void {
    if (Socket.initializing) return;
    Socket.initializing = true;

    // Check if we should use HTTP mode (Vercel deployment)
    if (isVercelEnvironment()) {
      Socket._httpMode = true;
      getToken()
        .then((token) => {
          Socket._token = token;
          toast.stickySuccess("ws", "Connected to server (HTTP mode).");
          Socket.initializing = false;
          Socket.callbacks.open?.forEach((callback) => {
            callback(new Event("open") as unknown as WebSocketEventMap["open"]);
          });
        })
        .catch(() => {
          const msg = `Connection failed. Retry...`;
          toast.stickyError("ws", msg);
          setTimeout(() => {
            Socket.initializing = false;
            Socket.tryInitialize();
          }, 1500);
        });
      return;
    }

    // Original WebSocket mode for local development
    getToken()
      .then((token) => {
        Socket._initialize(token);
      })
      .catch(() => {
        const msg = `Connection failed. Retry...`;
        toast.stickyError("ws", msg);

        setTimeout(() => {
          Socket.tryInitialize();
        }, 1500);
      });
  }

  private static _initialize(token: string): void {
    if (Socket.isConnected()) return;

    const WS_URL = `ws://${window.location.host}/ws?token=${token}`;
    Socket._socket = new WebSocket(WS_URL);

    Socket._socket.onopen = (e) => {
      toast.stickySuccess("ws", "Connected to server.");
      Socket.initializing = false;
      Socket.callbacks.open?.forEach((callback) => {
        callback(e);
      });
    };

    Socket._socket.onmessage = (e) => {
      handleAssistantMessage(e.data);
    };

    Socket._socket.onerror = () => {
      const msg = "Connection failed. Retry...";
      toast.stickyError("ws", msg);
    };

    Socket._socket.onclose = () => {
      // Reconnect after a delay
      setTimeout(() => {
        Socket.tryInitialize();
      }, 3000); // Reconnect after 3 seconds
    };
  }

  static isConnected(): boolean {
    if (Socket._httpMode) {
      return Socket._token !== "";
    }
    return (
      Socket._socket !== null && Socket._socket.readyState === WebSocket.OPEN
    );
  }

  static send(message: string): void {
    if (Socket._httpMode) {
      // HTTP mode: send via API endpoint
      Socket.sendHttpMessage(message);
      return;
    }

    // Original WebSocket mode
    if (!Socket.isConnected()) {
      Socket.tryInitialize();
    }
    if (Socket.initializing) {
      setTimeout(() => Socket.send(message), 1000);
      return;
    }

    if (Socket.isConnected()) {
      Socket._socket?.send(message);
    } else {
      const msg = "Connection failed. Retry...";
      toast.stickyError("ws", msg);
    }
  }

  private static async sendHttpMessage(message: string): Promise<void> {
    try {
      const data = JSON.parse(message);

      // Handle different action types
      if (data.action === "start") {
        // Send chat message via HTTP API
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${Socket._token}`,
          },
          body: JSON.stringify({
            message: data.args?.task || "",
            model: localStorage.getItem("LLM_MODEL") || "gpt-4",
          }),
        });

        const result = await response.json();

        if (result.error) {
          handleAssistantMessage(
            JSON.stringify({
              action: "finish",
              message: `Error: ${result.error}`,
            }),
          );
        } else {
          // Simulate the agent response
          handleAssistantMessage(
            JSON.stringify({
              action: "think",
              args: { thought: "Processing your request..." },
            }),
          );

          handleAssistantMessage(
            JSON.stringify({
              action: "finish",
              message: result.response,
            }),
          );
        }
      } else if (data.action === "initialize") {
        // Handle initialization
        handleAssistantMessage(
          JSON.stringify({
            action: "initialize",
          }),
        );
      }
    } catch (error) {
      console.error("HTTP send error:", error);
      handleAssistantMessage(
        JSON.stringify({
          action: "finish",
          message: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
        }),
      );
    }
  }

  static addEventListener(
    event: string,
    callback: (e: MessageEvent) => void,
  ): void {
    Socket._socket?.addEventListener(
      event as keyof WebSocketEventMap,
      callback as (
        this: WebSocket,
        ev: WebSocketEventMap[keyof WebSocketEventMap],
      ) => never,
    );
  }

  static removeEventListener(
    event: string,
    listener: (e: Event) => void,
  ): void {
    Socket._socket?.removeEventListener(event, listener);
  }

  static registerCallback<K extends keyof WebSocketEventMap>(
    event: K,
    callbacks: ((data: WebSocketEventMap[K]) => void)[],
  ): void {
    if (Socket.callbacks[event] === undefined) {
      return;
    }
    Socket.callbacks[event].push(...callbacks);
  }
}

Socket.tryInitialize();

export default Socket;
