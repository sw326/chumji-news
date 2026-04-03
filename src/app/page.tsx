import { fetchPostsPage } from "@/lib/data";
import NewsBoardClient from "@/components/NewsBoardClient";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { posts, hasMore } = await fetchPostsPage(0, "all");
  return <NewsBoardClient initialPosts={posts} initialHasMore={hasMore} />;
}
