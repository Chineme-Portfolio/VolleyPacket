import { avatarUrl } from "@/lib/api";
import { PRESET_IDS } from "@/lib/avatars";

interface AvatarProps {
  avatar?: string | null; // "preset:<id>" | "upload:<ver>" | null
  name?: string | null; // for the initials fallback
  userId?: string | null; // required to load an uploaded avatar
  size?: number; // px
  className?: string;
}

/** Renders a user's avatar: a chosen preset SVG, an uploaded image, or initials. */
export default function Avatar({ avatar, name, userId, size = 36, className = "" }: AvatarProps) {
  const box = { width: size, height: size };
  const base = `rounded-full flex items-center justify-center overflow-hidden flex-shrink-0 ${className}`;

  // Preset — bundled SVG (animal / alien / silhouette) on a soft circle
  if (avatar?.startsWith("preset:")) {
    const id = avatar.slice(7);
    if (PRESET_IDS.has(id)) {
      return (
        <div className={`${base} bg-gradient-to-br from-emerald-100 to-cyan-100`} style={box}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/avatars/${id}.svg`} alt="" style={{ width: size * 0.66, height: size * 0.66 }} />
        </div>
      );
    }
  }

  // Uploaded image — served publicly from the API (version busts the cache)
  if (avatar?.startsWith("upload:") && userId) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={avatarUrl(userId, avatar.slice(7))} alt="" className={`${base} object-cover bg-gray-100`} style={box} />
    );
  }

  // Initials fallback
  const initials = (name || "").trim() ? (name as string).trim().slice(0, 2).toUpperCase() : "VP";
  return (
    <div className={`${base} bg-green-700 text-white font-semibold`} style={{ ...box, fontSize: size * 0.4 }}>
      {initials}
    </div>
  );
}
