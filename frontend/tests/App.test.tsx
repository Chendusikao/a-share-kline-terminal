import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "../src/App";

describe("App", () => {
  it("identifies the terminal and its supported market data scope", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "A 股 K 线终端" }),
    ).toBeInTheDocument();
    expect(screen.getByText("仅支持 A 股前复权日线")).toBeInTheDocument();
  });

  it("keeps the data source and investment disclaimer visible", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByText("数据来源：AKShare")).toBeInTheDocument();
    expect(screen.getByText("不构成投资建议")).toBeInTheDocument();
  });
});
