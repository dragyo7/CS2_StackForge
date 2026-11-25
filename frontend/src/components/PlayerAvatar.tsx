import React from 'react';
import type { RoleType } from '../types';

interface Props {
  name: string;
  avatarUrl?: string | null;
  role?: RoleType | string | null;
  size?: number;
}

const ROLE_COLORS: Record<string, string> = {
  AWPer: '#e89b2d',
  IGL: '#38bdf8',
  Entry: '#f87171',
  Support: '#34d399',
  Lurker: '#a78bfa',
  Rifler: '#94a3b8',
};

export const PlayerAvatar: React.FC<Props> = ({ name, avatarUrl, role, size = 34 }) => {
  const initials = name
    .replace(/\[DEMO\]/gi, '')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('') || 'SF';

  const borderColor = (role && ROLE_COLORS[role]) || '#475569';

  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        width={size}
        height={size}
        style={{
          width: size,
          height: size,
          borderRadius: 6,
          objectFit: 'cover',
          border: `1.5px solid ${borderColor}`,
          flexShrink: 0,
        }}
      />
    );
  }

  return (
    <div
      aria-label={name}
      style={{
        width: size,
        height: size,
        borderRadius: 6,
        background: 'linear-gradient(145deg, #1b2434, #0f1520)',
        border: `1.5px solid ${borderColor}`,
        color: '#e2e8f0',
        display: 'grid',
        placeItems: 'center',
        fontSize: Math.max(11, Math.round(size * 0.36)),
        fontWeight: 700,
        fontFamily: "'Space Grotesk', sans-serif",
        flexShrink: 0,
        letterSpacing: '0.03em',
      }}
    >
      {initials}
    </div>
  );
};
