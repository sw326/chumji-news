import { getAllPosts } from "@/lib/data";
import NewsBoardClient from "@/components/NewsBoardClient";

export const dynamic = "force-dynamic";

export default async function Home() {
  const posts = await getAllPosts();
  return <NewsBoardClient posts={posts} />;
}
