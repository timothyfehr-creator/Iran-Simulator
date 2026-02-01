interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = 'h-4 w-full' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-war-room-border rounded ${className}`}
      aria-hidden="true"
    />
  );
}
