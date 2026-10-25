#include "third_party/meshoptimizer-v1.3/meshoptimizer.h"

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <stdexcept>
#include <vector>

#if !defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "The source mesh bins use little-endian uint32 indices; build on a little-endian host"
#endif

namespace {
constexpr size_t kVertexStride = 32;

size_t parseCount(const char* text, const char* label) {
	char* end = nullptr;
	errno = 0;
	unsigned long long value = std::strtoull(text, &end, 10);
	if (errno || !end || *end || value > std::numeric_limits<size_t>::max()) {
		throw std::runtime_error(std::string("invalid ") + label + ": " + text);
	}
	return static_cast<size_t>(value);
}

std::vector<unsigned char> readBytes(const std::string& path, size_t expected) {
	std::ifstream input(path, std::ios::binary | std::ios::ate);
	if (!input) throw std::runtime_error("could not open input: " + path);
	std::streamoff length = input.tellg();
	if (length < 0 || static_cast<unsigned long long>(length) != expected)
		throw std::runtime_error("input byte length does not match supplied vertex/index counts");
	std::vector<unsigned char> data(expected);
	input.seekg(0);
	if (expected && !input.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(expected)))
		throw std::runtime_error("short read from input: " + path);
	return data;
}

void writeBytes(const std::string& path, const std::vector<unsigned char>& data) {
	std::ofstream output(path, std::ios::binary | std::ios::trunc);
	if (!output || (!data.empty() && !output.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()))))
		throw std::runtime_error("could not write output: " + path);
}
}

int main(int argc, char** argv) {
	try {
		if (argc != 5) {
			std::cerr << "usage: meshopt_reindex INPUT OUTPUT VERTEX_COUNT INDEX_COUNT\n";
			return 2;
		}
		const std::string inputPath = argv[1];
		const std::string outputPath = argv[2];
		const size_t vertexCount = parseCount(argv[3], "vertex count");
		const size_t indexCount = parseCount(argv[4], "index count");
		if (vertexCount > std::numeric_limits<unsigned int>::max() || indexCount > std::numeric_limits<unsigned int>::max())
			throw std::runtime_error("mesh exceeds meshoptimizer's uint32 index range");
		if (vertexCount > std::numeric_limits<size_t>::max() / kVertexStride || indexCount > std::numeric_limits<size_t>::max() / sizeof(uint32_t))
			throw std::runtime_error("mesh byte size overflows host size_t");
		const size_t vertexBytes = vertexCount * kVertexStride;
		const size_t indexBytes = indexCount * sizeof(uint32_t);
		if (vertexBytes > std::numeric_limits<size_t>::max() - indexBytes)
			throw std::runtime_error("mesh byte size overflows host size_t");
		std::vector<unsigned char> source = readBytes(inputPath, vertexBytes + indexBytes);
		const unsigned char* sourceVertices = source.data();
		std::vector<uint32_t> sourceIndices(indexCount);
		if (indexBytes) std::memcpy(sourceIndices.data(), source.data() + vertexBytes, indexBytes);
		for (size_t i = 0; i < indexCount; ++i)
			if (sourceIndices[i] >= vertexCount) throw std::runtime_error("source index is outside the supplied vertex range");

		std::vector<unsigned int> dedupRemap(vertexCount);
		size_t dedupCount = meshopt_generateVertexRemap(dedupRemap.data(), sourceIndices.data(), indexCount,
			sourceVertices, vertexCount, kVertexStride);
		std::vector<uint32_t> dedupIndices(indexCount);
		meshopt_remapIndexBuffer(dedupIndices.data(), sourceIndices.data(), indexCount, dedupRemap.data());
		std::vector<unsigned char> dedupVertices(dedupCount * kVertexStride);
		meshopt_remapVertexBuffer(dedupVertices.data(), sourceVertices, vertexCount, kVertexStride, dedupRemap.data());

		// Vertex-fetch remapping traverses the existing index stream in order.
		// It changes only vertex numbering and preserves triangle/submesh order.
		std::vector<unsigned int> fetchRemap(dedupCount);
		size_t fetchedCount = meshopt_optimizeVertexFetchRemap(fetchRemap.data(), dedupIndices.data(), indexCount, dedupCount);
		std::vector<uint32_t> outputIndices(indexCount);
		meshopt_remapIndexBuffer(outputIndices.data(), dedupIndices.data(), indexCount, fetchRemap.data());
		std::vector<unsigned char> outputVertices(fetchedCount * kVertexStride);
		meshopt_remapVertexBuffer(outputVertices.data(), dedupVertices.data(), dedupCount, kVertexStride, fetchRemap.data());

		std::vector<unsigned char> output;
		output.reserve(outputVertices.size() + outputIndices.size() * sizeof(uint32_t));
		output.insert(output.end(), outputVertices.begin(), outputVertices.end());
		const unsigned char* indexData = reinterpret_cast<const unsigned char*>(outputIndices.data());
		output.insert(output.end(), indexData, indexData + outputIndices.size() * sizeof(uint32_t));
		writeBytes(outputPath, output);
		std::cout << "source_vertices=" << vertexCount << " optimized_vertices=" << fetchedCount
			<< " indices=" << indexCount << " bytes_in=" << source.size() << " bytes_out=" << output.size() << '\n';
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "meshopt_reindex: " << error.what() << '\n';
		return 1;
	}
}
