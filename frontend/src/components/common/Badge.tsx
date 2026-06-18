type BadgeProps = {
  children: React.ReactNode;
  tone?: string;
};

export function Badge({ children, tone = "closed" }: BadgeProps) {
  return <span className={`badge ${tone.toLowerCase()}`}>{children}</span>;
}
