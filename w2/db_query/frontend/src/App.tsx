import { Refine } from "@refinedev/core";
import routerProvider from "@refinedev/react-router";
import { ConfigProvider } from "antd";

function App() {
  return (
    <ConfigProvider>
      <Refine
        routerProvider={routerProvider}
        resources={[
          { name: "databases", list: "/databases", create: "/databases/create", show: "/databases/:id" },
          { name: "query", list: "/query" },
        ]}
      />
    </ConfigProvider>
  );
}

export default App;
