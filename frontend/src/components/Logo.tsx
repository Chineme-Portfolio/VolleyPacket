/** Inline SVG logo — icon-only and full wordmark variants */

export function LogoIcon({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
    >
      <defs>
        <linearGradient id="liGrad" x1="30%" y1="20%" x2="70%" y2="80%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#065f46" />
        </linearGradient>
        <linearGradient id="liSwish" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Swish trails */}
      <path d="M 8 68 Q 20 62, 30 58" stroke="url(#liSwish)" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.5" />
      <path d="M 5 78 Q 18 72, 32 66" stroke="url(#liSwish)" strokeWidth="2.5" fill="none" strokeLinecap="round" opacity="0.4" />
      <path d="M 10 88 Q 22 80, 36 74" stroke="url(#liSwish)" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.3" />

      {/* Ball */}
      <circle cx="65" cy="58" r="38" fill="url(#liGrad)" />

      {/* Seam lines */}
      <path d="M 27 58 Q 45 45, 65 44 Q 85 43, 103 58" stroke="white" strokeWidth="1.8" fill="none" opacity="0.35" strokeLinecap="round" />
      <path d="M 27 58 Q 45 71, 65 72 Q 85 73, 103 58" stroke="white" strokeWidth="1.8" fill="none" opacity="0.35" strokeLinecap="round" />
      <path d="M 65 20 Q 52 35, 50 58 Q 48 81, 65 96" stroke="white" strokeWidth="1.8" fill="none" opacity="0.35" strokeLinecap="round" />
      <path d="M 42 25 Q 38 40, 40 58 Q 42 76, 50 92" stroke="white" strokeWidth="1.5" fill="none" opacity="0.25" strokeLinecap="round" />
      <path d="M 88 25 Q 92 40, 90 58 Q 88 76, 80 92" stroke="white" strokeWidth="1.5" fill="none" opacity="0.25" strokeLinecap="round" />

      {/* Paper airplane */}
      <g transform="translate(58, 38) rotate(-15)">
        <polygon points="0,12 28,-2 8,8" fill="white" opacity="0.95" />
        <polygon points="8,8 28,-2 12,18" fill="white" opacity="0.75" />
      </g>
    </svg>
  );
}

export function LogoFull({ height = 32, className = "" }: { height?: number; className?: string }) {
  const width = Math.round((580 / 80) * height);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 580 80"
      width={width}
      height={height}
      className={className}
    >
      <defs>
        <linearGradient id="lfGrad" x1="30%" y1="20%" x2="70%" y2="80%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#065f46" />
        </linearGradient>
        <linearGradient id="lfSwish" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* V */}
      <text x="0" y="60" fontFamily="Inter, Arial, Helvetica, sans-serif" fontWeight="800" fontSize="52" fill="#1f2937" letterSpacing="-1">V</text>

      {/* "O" = volleyball icon */}
      <g transform="translate(35, 8)">
        <path d="M -8 42 Q -2 38, 4 36" stroke="url(#lfSwish)" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.5" />
        <path d="M -10 50 Q -3 46, 5 43" stroke="url(#lfSwish)" strokeWidth="1.8" fill="none" strokeLinecap="round" opacity="0.4" />
        <path d="M -7 58 Q -1 53, 7 50" stroke="url(#lfSwish)" strokeWidth="1.5" fill="none" strokeLinecap="round" opacity="0.3" />

        <circle cx="30" cy="34" r="26" fill="url(#lfGrad)" />

        <path d="M 4 34 Q 16 24, 30 23 Q 44 22, 56 34" stroke="white" strokeWidth="1.2" fill="none" opacity="0.35" strokeLinecap="round" />
        <path d="M 4 34 Q 16 44, 30 45 Q 44 46, 56 34" stroke="white" strokeWidth="1.2" fill="none" opacity="0.35" strokeLinecap="round" />
        <path d="M 30 8 Q 22 20, 20 34 Q 18 48, 30 60" stroke="white" strokeWidth="1.2" fill="none" opacity="0.35" strokeLinecap="round" />
        <path d="M 16 11 Q 13 22, 14 34 Q 15 46, 22 57" stroke="white" strokeWidth="1" fill="none" opacity="0.25" strokeLinecap="round" />
        <path d="M 44 11 Q 47 22, 46 34 Q 45 46, 38 57" stroke="white" strokeWidth="1" fill="none" opacity="0.25" strokeLinecap="round" />

        <g transform="translate(22, 22) rotate(-15) scale(0.7)">
          <polygon points="0,12 28,-2 8,8" fill="white" opacity="0.95" />
          <polygon points="8,8 28,-2 12,18" fill="white" opacity="0.75" />
        </g>
      </g>

      {/* LLEY */}
      <text x="92" y="60" fontFamily="Inter, Arial, Helvetica, sans-serif" fontWeight="800" fontSize="52" fill="#1f2937" letterSpacing="-1">LLEY</text>
      {/* PACKET in green */}
      <text x="260" y="60" fontFamily="Inter, Arial, Helvetica, sans-serif" fontWeight="800" fontSize="52" fill="#065f46" letterSpacing="-1">PACKET</text>
    </svg>
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
