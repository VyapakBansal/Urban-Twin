type Props = {
  onOpen: () => void;
};

export function MobileChrome({ onOpen }: Props) {
  return (
    <button
      type="button"
      className="mobile-layers-btn"
      onClick={onOpen}
      aria-label="Open layers"
    >
      Layers
    </button>
  );
}
