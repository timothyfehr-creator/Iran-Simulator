import { Map } from 'lucide-react';

export function MapPlaceholder() {
  return (
    <div
      className="
        flex flex-col items-center justify-center
        min-h-[300px] lg:min-h-[400px]
        bg-[#1a1a2e] rounded-lg
        border border-war-room-border
        relative overflow-hidden
      "
      aria-label="Map view placeholder"
    >
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: `
            linear-gradient(to right, #3b82f6 1px, transparent 1px),
            linear-gradient(to bottom, #3b82f6 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
      />

      {/* Content */}
      <div className="relative z-10 text-center">
        <Map className="w-16 h-16 text-gray-600 mx-auto mb-4" />
        <p className="text-gray-500 font-mono text-sm uppercase tracking-wider">
          Map View
        </p>
        <p className="text-gray-600 text-xs mt-1">Coming Soon</p>
      </div>

      {/* Subtle glow effect */}
      <div className="absolute inset-0 bg-gradient-radial from-war-room-accent/5 to-transparent pointer-events-none" />
    </div>
  );
}
