\
import { useQuery } from "@tanstack/react-query";
import axios from "axios";

export default function WaitingRoom() {
  const { data } = useQuery({
    queryKey: ["waiting-room"],
    queryFn: async () => (await axios.get("/api/public/waiting-room/")).data,
    refetchInterval: 5000,
  });

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col p-8 font-sans">
      <header className="flex justify-between items-center border-b border-slate-700 pb-4 mb-8">
        <div className="text-3xl font-bold text-sky-400">Nimbus OPD Cloud</div>
        <div className="text-xl text-slate-400">{new Date().toLocaleTimeString()}</div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 flex-1">
        <div className="flex flex-col items-center">
          <h2 className="text-4xl font-extrabold text-emerald-400 mb-8 tracking-wider">
            NOW SERVING
          </h2>
          <div className="w-full space-y-6">
            {!data?.now_serving || data.now_serving.length === 0 ? (
              <div className="text-center text-slate-500 text-2xl mt-12">
                Waiting for next patient…
              </div>
            ) : (
              data.now_serving.map((item: any) => (
                <div
                  key={item.token}
                  className="bg-emerald-900/40 border-2 border-emerald-500 rounded-2xl p-8 flex justify-between items-center animate-pulse"
                >
                  <div>
                    <div className="text-6xl font-black text-white">{item.token}</div>
                    <div className="text-2xl text-emerald-200 mt-2">{item.patient}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-white">{item.doctor}</div>
                    <div className="text-emerald-300">Room 1</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex flex-col">
          <h2 className="text-3xl font-bold text-sky-400 mb-8 tracking-wider">
            WAITING QUEUE
          </h2>
          <div className="bg-slate-800 rounded-2xl p-6 flex-1">
            {!data?.waiting || data.waiting.length === 0 ? (
              <div className="text-center text-slate-500 text-xl mt-12">
                Queue is empty.
              </div>
            ) : (
              <ul className="space-y-4">
                {data.waiting.map((item: any, idx: number) => (
                  <li
                    key={item.token}
                    className="flex justify-between items-center text-xl border-b border-slate-700 pb-3"
                  >
                    <div className="flex items-center gap-4">
                      <span className="text-slate-500 font-mono text-lg">{idx + 1}.</span>
                      <span className="font-bold text-white">{item.token}</span>
                      <span className="text-slate-400">{item.patient}</span>
                    </div>
                    <span className="text-slate-500">{item.doctor}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <footer className="mt-8 text-center text-slate-500">
        Please keep an eye on this screen. You will be called shortly.
      </footer>
    </div>
  );
}
