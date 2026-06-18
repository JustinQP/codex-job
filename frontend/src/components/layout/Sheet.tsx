import { Button } from "../common/Button";

type SheetProps = {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
};

export function Sheet({ title, children, onClose }: SheetProps) {
  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <section
        aria-label={title}
        className="sheet"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="row">
          <h2>{title}</h2>
          <Button onClick={onClose} variant="text">
            关闭
          </Button>
        </div>
        {children}
      </section>
    </div>
  );
}
