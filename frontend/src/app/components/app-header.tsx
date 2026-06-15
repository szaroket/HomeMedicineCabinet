import logo from "@/assets/logo.png";

export function AppHeader() {
  return (
    <div className="flex items-center gap-3">
      <img src={logo} alt="Domowa apteczka" className="h-8 w-8" />
      <span className="text-lg font-semibold text-white">Apteczka domowa</span>
    </div>
  );
}
