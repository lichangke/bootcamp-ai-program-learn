import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { TicketListPage } from "@/components/TicketListPage";
import { ToastProvider } from "@/components/ToastProvider";

function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TicketListPage />
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default App;
