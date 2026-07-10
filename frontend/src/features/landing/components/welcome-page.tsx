import { Link } from "react-router-dom";
import logo from "@/assets/logo.png";
import { AppFooter } from "@/app/components/app-footer";

interface Highlight {
  title: string;
  description: string;
}

const HIGHLIGHTS: Highlight[] = [
  {
    title: "Czyste dane z rejestru",
    description:
      "leki dodajesz z oficjalnego polskiego rejestru, więc nazwy i dane są zawsze spójne.",
  },
  {
    title: "Przypomnienia o terminach i zapasach",
    description:
      "dostajesz powiadomienia, gdy leki tracą ważność lub zapas ważnego leku spada poniżej minimum.",
  },
  {
    title: "Śledzenie dawkowania",
    description:
      "ustaw harmonogram i zobacz szacowaną datę, kiedy skończy się lek, który aktualnie przyjmujesz.",
  },
  {
    title: "Panel w jednym miejscu",
    description:
      "widzisz stan apteczki na skróty: ważne, kończące się i przeterminowane leki.",
  },
];

function HighlightCard({ title, description }: Highlight) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
      <h3 className="mb-1 text-base font-semibold text-slate-200">{title}</h3>
      <p className="text-sm text-slate-400">{description}</p>
    </div>
  );
}

export function WelcomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-900">
      <div className="flex flex-1 flex-col items-center px-4 pt-16 sm:pt-24">
        <div className="mb-3 flex flex-col items-center gap-0">
          <img src={logo} alt="Apteczka domowa" className="h-16 w-16" />
          <h1 className="my-0 whitespace-nowrap text-center text-2xl font-bold text-white">
            Apteczka domowa
          </h1>
        </div>
        <p className="mt-1 max-w-xl text-center text-sm text-slate-400">
          Prowadź domową apteczkę w jednym miejscu — śledź terminy ważności,
          zapasy i dawkowanie leków, tak aby niczego nie zabrakło w kluczowym
          momencie.
        </p>

        <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
          {HIGHLIGHTS.map((highlight) => (
            <HighlightCard key={highlight.title} {...highlight} />
          ))}
        </div>

        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
          <Link
            to="/register"
            className="rounded-md bg-blue-600 px-6 py-2 text-center font-semibold text-white hover:bg-blue-500"
          >
            Zarejestruj się
          </Link>
          <Link
            to="/login"
            className="rounded-md border border-slate-700 px-6 py-2 text-center font-semibold text-slate-200 hover:bg-slate-800"
          >
            Zaloguj się
          </Link>
        </div>
      </div>
      <AppFooter />
    </div>
  );
}
