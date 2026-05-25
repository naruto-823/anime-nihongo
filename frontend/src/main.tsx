import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";
import { SpeakerProvider } from "./lib/speaker-context";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <SpeakerProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SpeakerProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
