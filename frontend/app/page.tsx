"use client";

import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { AppDataProvider } from "@/state/AppData";
import { PriceStreamProvider } from "@/state/PriceStream";

export default function Page() {
  return (
    <PriceStreamProvider>
      <AppDataProvider>
        <div className="flex h-full flex-col">
          <Header />

          <main className="flex min-h-0 flex-1 gap-2 p-2">
            <div className="w-[210px] shrink-0 xl:w-[260px]">
              <Watchlist />
            </div>

            <div className="grid min-w-0 flex-1 grid-rows-[1.15fr_1fr_1fr] gap-2">
              <MainChart />
              <div className="grid min-h-0 grid-cols-2 gap-2">
                <Heatmap />
                <PnlChart />
              </div>
              <PositionsTable />
            </div>

            <ChatPanel />
          </main>

          <TradeBar />
        </div>
      </AppDataProvider>
    </PriceStreamProvider>
  );
}
