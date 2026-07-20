import type { Theme } from "../hooks/useTheme";

type Props = {
  theme: Theme;
  onToggleTheme: () => void;
};

export function BrandBar({ theme, onToggleTheme }: Props) {
  return (
    <header className="brand-bar">
      <div className="brand-row">
        <div>
          <p className="brand">Urban Twin</p>
          <p className="place">Kensington · Calgary</p>
        </div>
        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={
            theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
          }
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>
    </header>
  );
}
