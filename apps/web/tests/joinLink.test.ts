import {
  consumeJoinFragment,
  defaultDeviceName,
  detectPlatform,
  parseJoinFragment,
} from "../src/features/pairing/joinLink";

const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1";
const IPADOS = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15";
const PIXEL =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36";
const REDUCED_UA =
  "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36";

describe("parseJoinFragment", () => {
  it("lit l'identifiant de session et le secret", () => {
    expect(parseJoinFragment("#/join?s=abc&k=s3cr-et_")).toEqual({
      sessionId: "abc",
      secret: "s3cr-et_",
    });
  });

  it.each(["", "#/", "#/join", "#/join?s=abc", "#/send?s=a&k=b"])("ignore « %s »", (hash) => {
    expect(parseJoinFragment(hash)).toBeNull();
  });
});

describe("consumeJoinFragment", () => {
  it("efface le secret de l'URL et de l'historique", () => {
    window.history.replaceState(null, "", "/#/join?s=sess&k=secret123");
    expect(consumeJoinFragment()).toEqual({ sessionId: "sess", secret: "secret123" });
    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain("secret123");
  });

  it("ne touche pas à une URL sans appairage", () => {
    window.history.replaceState(null, "", "/#/autre");
    expect(consumeJoinFragment()).toBeNull();
    expect(window.location.hash).toBe("#/autre");
  });
});

describe("plateforme et nom d'appareil", () => {
  it.each([
    [IPHONE, 0, "ios", "iPhone"],
    [IPADOS, 5, "ios", "iPad"],
    [PIXEL, 5, "android", "Pixel 8"],
    [REDUCED_UA, 5, "android", "Téléphone Android"],
    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", 0, "windows", "Appareil"],
  ] as const)("%s", (ua, touch, platform, name) => {
    expect(detectPlatform(ua, touch)).toBe(platform);
    expect(defaultDeviceName(ua, touch)).toBe(name);
  });
});
