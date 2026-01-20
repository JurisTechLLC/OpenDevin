/**
 * Helper function to transform VS Code URLs
 *
 * This function checks if a VS Code URL points to localhost and replaces it with
 * the current window's hostname if they don't match. It also transforms the protocol
 * from HTTP to HTTPS when the main page is served over HTTPS to prevent mixed content
 * errors.
 *
 * @param vsCodeUrl The original VS Code URL from the backend
 * @returns The transformed URL with the correct hostname and protocol
 */
export function transformVSCodeUrl(vsCodeUrl: string | null): string | null {
  if (!vsCodeUrl) return null;

  try {
    const url = new URL(vsCodeUrl);
    let urlModified = false;

    // Check if the URL points to localhost
    if (
      url.hostname === "localhost" &&
      window.location.hostname !== "localhost"
    ) {
      // Replace localhost with the current hostname
      url.hostname = window.location.hostname;
      urlModified = true;
    }

    // Transform HTTP to HTTPS when the main page is served over HTTPS
    // This prevents mixed content errors when embedding the VSCode iframe
    if (url.protocol === "http:" && window.location.protocol === "https:") {
      url.protocol = "https:";
      urlModified = true;
    }

    return urlModified ? url.toString() : vsCodeUrl;
  } catch {
    // Silently handle the error and return the original URL
    return vsCodeUrl;
  }
}
