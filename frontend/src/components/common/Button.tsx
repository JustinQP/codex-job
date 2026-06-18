type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "text" | "danger";
};

const variantClass = {
  primary: "btn-primary",
  secondary: "secondary",
  text: "btn-text",
  danger: "danger"
};

export function Button({
  variant = "secondary",
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={`${variantClass[variant]} ${className}`.trim()}
      type={type}
    />
  );
}
