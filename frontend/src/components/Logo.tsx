/** Logo components using generated PNG assets */
import Image from "next/image";

/** Icon-only logo (volleyball + paper airplane) */
export function LogoIcon({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logo-icon.png"
      alt="VolleyPacket"
      width={size}
      height={size}
      className={`object-contain ${className}`}
      priority
    />
  );
}

/** 3D icon logo */
export function LogoIcon3D({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logo-icon-3d.png"
      alt="VolleyPacket"
      width={size}
      height={size}
      className={`object-contain ${className}`}
    />
  );
}

/** Full wordmark (2D flat) */
export function LogoFull({ height = 32, className = "" }: { height?: number; className?: string }) {
  // Aspect ratio of the 2D wordmark: ~4.78:1
  const width = Math.round(height * 4.78);
  return (
    <Image
      src="/logo-full.png"
      alt="VolleyPacket"
      width={width}
      height={height}
      className={`object-contain ${className}`}
      priority
    />
  );
}

/** 3D wordmark */
export function LogoFull3D({ height = 32, className = "" }: { height?: number; className?: string }) {
  // Aspect ratio of the 3D wordmark: ~2.6:1
  const width = Math.round(height * 2.6);
  return (
    <Image
      src="/logo-full-3d.png"
      alt="VolleyPacket"
      width={width}
      height={height}
      className={`object-contain ${className}`}
    />
  );
}

/** Simple text+icon combo for tight spaces (sidebar, mobile) */
export function LogoCompact({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <LogoIcon size={36} />
      <div className="flex items-baseline gap-0">
        <span className="text-xl font-extrabold text-gray-900 tracking-tight">Volley</span>
        <span className="text-xl font-extrabold text-green-800 tracking-tight">Packet</span>
      </div>
    </div>
  );
}
