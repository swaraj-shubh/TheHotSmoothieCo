import { notFound } from "next/navigation"

/** Any unknown URL renders the design's 404 inside the site chrome. */
export default function Missing(): never {
  notFound()
}
