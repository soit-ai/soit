import type { Route } from "../routes/+types/home";
import { Welcome } from "../welcome/welcome";
import { useNavigate } from "@/hooks/use-navigate"
import { useEffect } from "react";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "New React Router App" },
    { name: "description", content: "Welcome to React Router!" },
  ];
}

export default function Home() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate("/chat");
  }, [navigate]);

  return <Welcome />;
}
