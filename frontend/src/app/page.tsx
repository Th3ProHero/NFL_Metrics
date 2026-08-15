import { redirect } from "next/navigation";

/** Home page redirects to the Live Games dashboard */
export default function HomePage() {
  redirect("/live");
}
